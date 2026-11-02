"""Trusted LoRA shapes from the exact supported base revisions, never remote manifests."""
# Qwen: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/raw/cdbee75f17c01a7cc42f958dc650907174af0554/config.json
# q_proj output = 32 attention heads * 128 head dim; v_proj = 8 KV heads * 128.
# Smol is retained only for the real offline CPU shared-core verification.
TOPOLOGIES = {
    ('Qwen/Qwen3-4B-Instruct-2507', 'cdbee75f17c01a7cc42f958dc650907174af0554'): (36, 2560, 4096, 1024),
    ('HuggingFaceTB/SmolLM2-135M-Instruct', '12fd25f77366fa6b3b4b768ec3050bf629380bac'): (30, 576, 576, 192),
}


def lora_shapes(base, rank):
    layers, hidden, q_width, v_width = TOPOLOGIES[(base['id'], base['revision'])]
    shapes = {}
    for layer in range(layers):
        for module, width in (('q_proj', q_width), ('v_proj', v_width)):
            prefix = f'base_model.model.model.layers.{layer}.self_attn.{module}.lora_'
            shapes[prefix + 'A.weight'] = [rank, hidden]
            shapes[prefix + 'B.weight'] = [width, rank]
    return shapes
