# DLSS 5 neural rendering on an AMD GPU: the network every 4th frame, split over 4 frames

Comparison page: https://zgauthier2000.github.io/dlss5-amd-split/

DLSS 5 neural rendering (small model) on an RX 7800 XT under Linux/Proton, before the upscaler. The network runs once every 4 frames, that run is split into 4 parts so every frame costs about the same, and its result is carried forward along the game's motion vectors in between, with fixes where it no longer fits (revealed background, scene cuts, the frame's edges, changed lighting).

- Source: branch [split-preview](https://github.com/zgauthier2000/dlss5-amd-split/tree/split-preview) (DLSSNR-AMD 0.0.9 plus these changes)
- Linux preview package (RDNA3, experimental): [0.0.9-split.1](https://github.com/zgauthier2000/dlss5-amd-split/releases/tag/v0.0.9-split.1)
- The earlier comparison page (2026-11-21, "as found vs ours"): [2026-11-21/](https://zgauthier2000.github.io/dlss5-amd-split/2026-11-21/)

Frames come from captured game clips run through the plugin's own runtime in a test harness; the display mapping is ours, not the game's tone mapping. Built on [DLSSNR-AMD](https://github.com/TheAutomatic/DLSSNR-AMD) and the RDNA3 ports by mauri870 ([DLSSNR-RDNA3](https://github.com/mauri870/DLSSNR-RDNA3)) and hedonemaeda. This project is not affiliated with, endorsed by or supported by NVIDIA or AMD. DLSS is a trademark of NVIDIA Corporation. No NVIDIA files or network weights are in this repository.
