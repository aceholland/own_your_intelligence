"""Same-origin API for a single-owner loopback development app."""
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .engine import OllamaEngine
from .retrieval import build_messages
from .store import Problem, Store, text


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class WorkspaceBody(Body):
    name: str


class JobBody(Body):
    name: str
    goal: str


class EditBody(Body):
    revision: int
    changes: dict


class SourceBody(Body):
    title: str
    content: str


class ExampleBody(Body):
    kind: str
    input: str
    output: str


class TryBody(Body):
    input: str
    mode: str = 'draft'


class CorrectionBody(Body):
    output: str


class ReviewBody(Body):
    check_id: str
    review: str


class ActivateBody(Body):
    version_id: str


def create_app(data_dir, engine=None):
    store = Store(Path(data_dir) / 'own.sqlite3')
    store.interrupt_evaluations()
    engine = engine or OllamaEngine()
    token = secrets.token_urlsafe(32)
    inference_lock = threading.Lock()
    web = Path(__file__).resolve().parent.parent / 'web'

    @asynccontextmanager
    async def lifespan(app):
        yield
        store.close()

    app = FastAPI(title='Own local workbench', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store = store

    @app.middleware('http')
    async def local_boundary(request: Request, call_next):
        host = request.headers.get('host', '')
        try:
            hostname = urlsplit('http://' + host).hostname
        except ValueError:
            hostname = None
        if hostname not in ('127.0.0.1', 'localhost', '::1'):
            return JSONResponse({'error': 'Open Own using its localhost address.'}, status_code=403)
        origin = request.headers.get('origin')
        if request.url.path.startswith('/api/'):
            if origin and origin != f'{request.url.scheme}://{host}':
                return JSONResponse({'error': 'Requests must come from the Own app.'}, status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'error': 'Open this action in the Own app.'}, status_code=403)
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and not secrets.compare_digest(request.headers.get('x-own-token', ''), token):
                return JSONResponse({'error': 'Your local session changed. Refresh the page and try again.'}, status_code=403)
            length = request.headers.get('content-length', '0')
            if not length.isdigit() or int(length) > 1200000:
                return JSONResponse({'error': 'Choose a file smaller than 1 MB.'}, status_code=413)
        response = await call_next(request)
        response.headers.update({'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            'Cache-Control': 'no-store'})
        return response

    @app.exception_handler(Problem)
    async def problem_handler(request, error):
        return JSONResponse({'error': str(error)}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, error):
        return JSONResponse({'error': 'Some information is missing or has the wrong format. Check the form and try again.'}, status_code=400)

    def generate(snapshot, user_input):
        model = snapshot['job']['model']
        if not model:
            raise Problem('Choose a local model in Teach it before trying this job.')
        available = engine.status()
        if not available['connected'] or model not in [m['name'] for m in available['models']]:
            raise Problem('The selected local model is not ready. Open AI connection and check Ollama.', 503)
        messages, references = build_messages(snapshot, user_input)
        start = time.monotonic()
        output = engine.chat(model, messages)
        return output, references, round((time.monotonic() - start) * 1000)

    @app.get('/api/bootstrap')
    def bootstrap():
        return {'csrf_token': token, 'workspaces': store.list_workspaces(),
                'capabilities': {'local_inference': True, 'weight_training': False, 'model_weights_export': False, 'multi_user_auth': False}}

    @app.get('/api/engine')
    def engine_status():
        return engine.status()

    @app.post('/api/workspaces')
    def create_workspace(body: WorkspaceBody):
        return store.create_workspace(body.name)

    @app.get('/api/workspaces/{ws}')
    def get_workspace(ws: str):
        return store.workspace(ws)

    @app.post('/api/workspaces/{ws}/jobs')
    def create_job(ws: str, body: JobBody):
        return store.create_job(ws, body.name, body.goal)

    @app.get('/api/workspaces/{ws}/jobs/{job}')
    def get_job(ws: str, job: str):
        return store.job(ws, job)

    @app.patch('/api/workspaces/{ws}/jobs/{job}')
    def edit_job(ws: str, job: str, body: EditBody):
        return store.update_job(ws, job, body.changes, body.revision)

    @app.post('/api/workspaces/{ws}/sources')
    def add_source(ws: str, body: SourceBody):
        return store.add_source(ws, body.title, body.content)

    @app.post('/api/workspaces/{ws}/upload')
    async def upload(ws: str, file: UploadFile = File(...)):
        name = (file.filename or '').replace('\\', '/').split('/')[-1]
        if Path(name).suffix.lower() not in ('.txt', '.md', '.csv'):
            raise Problem('Use a .txt, .md or .csv file. PDF and Word support comes in a later step.')
        content = await file.read(1048577)
        await file.close()
        if len(content) > 1048576:
            raise Problem('Choose a text file smaller than 1 MB.', 413)
        try:
            decoded = content.decode('utf-8-sig')
        except UnicodeDecodeError as error:
            raise Problem('This file is not UTF-8 text. Save it as UTF-8 and try again.') from error
        return store.add_source(ws, name, decoded)

    @app.post('/api/workspaces/{ws}/jobs/{job}/examples')
    def add_example(ws: str, job: str, body: ExampleBody):
        return store.add_example(ws, job, body.kind, body.input, body.output)

    @app.post('/api/workspaces/{ws}/jobs/{job}/try')
    def try_job(ws: str, job: str, body: TryBody):
        user_input = text(body.input, 'Request', 4000)
        snapshot, version_id = store.resolve_snapshot(ws, job, body.mode)
        if not inference_lock.acquire(blocking=False):
            raise Problem('Your local model is already working. Wait for it to finish and try again.', 409)
        try:
            output, references, duration = generate(snapshot, user_input)
            return store.record_run(ws, job, snapshot, user_input, output, references, duration, version_id)
        finally:
            inference_lock.release()

    @app.post('/api/workspaces/{ws}/jobs/{job}/runs/{run}/correction')
    def correct_run(ws: str, job: str, run: str, body: CorrectionBody):
        return store.correct_run(ws, job, run, body.output)

    def evaluate(ws, job, snapshot, evaluation):
        try:
            for check in snapshot['checks']:
                try:
                    output, _, _ = generate(snapshot, check['input'])
                    error = None
                except Problem as problem:
                    output, error = '', str(problem)
                except Exception:
                    output, error = '', 'This check could not finish. Check the AI connection and run checks again.'
                store.finish_check(ws, job, evaluation['id'], check['id'], output, error)
        finally:
            store.finish_evaluation(ws, job, evaluation['id'])
            inference_lock.release()

    @app.post('/api/workspaces/{ws}/jobs/{job}/evaluations')
    def run_checks(ws: str, job: str, background: BackgroundTasks):
        snapshot = store.snapshot(ws, job)
        if not snapshot['checks']:
            raise Problem('Add a separate check example first.')
        if not snapshot['job']['model']:
            raise Problem('Choose a local model in Teach it first.')
        if not inference_lock.acquire(blocking=False):
            raise Problem('Your local model is already working. Wait for it to finish.', 409)
        try:
            evaluation = store.begin_evaluation(ws, job, snapshot)
            background.add_task(evaluate, ws, job, snapshot, evaluation)
            return evaluation
        except Exception:
            inference_lock.release()
            raise

    @app.post('/api/workspaces/{ws}/jobs/{job}/evaluations/{evaluation}/review')
    def review_check(ws: str, job: str, evaluation: str, body: ReviewBody):
        return store.review_check(ws, job, evaluation, body.check_id, body.review)

    @app.post('/api/workspaces/{ws}/jobs/{job}/approve')
    def approve(ws: str, job: str):
        return store.approve(ws, job)

    @app.post('/api/workspaces/{ws}/jobs/{job}/activate')
    def activate(ws: str, job: str, body: ActivateBody):
        return store.activate(ws, job, body.version_id)

    @app.get('/api/workspaces/{ws}/export')
    def export_workspace(ws: str):
        return Response(store.export_workspace(ws), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="own-workspace.zip"'})

    @app.get('/api/workspaces/{ws}/jobs/{job}/training')
    def export_training(ws: str, job: str):
        return Response(store.training_jsonl(ws, job), media_type='application/x-ndjson', headers={'Content-Disposition': 'attachment; filename="teaching-examples.jsonl"'})

    @app.get('/')
    def index():
        return FileResponse(web / 'index.html')

    @app.get('/{asset}')
    def asset(asset: str):
        if asset not in ('app.js', 'styles.css', 'mark.svg'):
            return JSONResponse({'error': 'Page not found. Open the app home page.'}, status_code=404)
        return FileResponse(web / asset)

    return app
