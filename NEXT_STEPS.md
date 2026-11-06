# Next milestone: use the larger trained model in Try it

The repository includes the redesigned Acewyn AI workbench, CPU model training, and the free Colab notebook and result-import workflow.

Two real fictional-shop Colab runs were completed on a free Tesla T4 and imported into Acewyn AI. The first trained adapter answered delivery with “3-5 working days.” After adding more teaching examples, the next adapter answered “Standard delivery takes five working days.” The receipt check also matched its expected policy. Both runs remain available for human review.

## Build next

1. Test a compatible local serving format for the larger trained adapter on the 16 GB development laptop, including memory use, response time, and output quality.
2. Add the larger model to **Try it** only once its actual inference path works. Preserve the recorded base identity, adapter, frozen examples, and comparison history.
3. Evaluate fresh questions, including policy boundaries, ambiguous requests, and questions the business has not answered.
4. Connect selection, checks, approval, and version switching to the verified serving path.

CPU-trained starter models already support this lifecycle. Colab-trained Qwen adapters currently support comparison and export, with an independent CUDA runner.

## Cost and execution

The founder requires zero out-of-pocket spend. Keep training interactive in Colab using an available free GPU. If capacity is unavailable, use local CPU training or try again later.

The optional Modal integration remains available, with its first real L4 execution unverified. Local billing assumptions or a saved account connection do not authorize paid compute.
