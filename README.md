# DLSS 5 neural rendering on an AMD GPU: frame reuse, as found vs ours

Comparison page: https://zgauthier2000.github.io/dlss5-amd-split/

DLSS 5 neural rendering (small model) on an RX 7800 XT under Linux/Proton, run every 4th frame before FSR 4.1.2 Lite (4.1.2l-lossy). The community plugin, as found, runs the whole network on one frame in four; our version spreads it over all four frames, times it to the upscaler's skipped frames, and cleans up the reused result at screen edges, around moving characters and at scene cuts. All fps figures on the page are rough estimates.

Frames come from captured game clips; the display mapping is ours, not the game's tone mapping. The DLSS 5 network runs through the community AMD port ([mauri870/DLSSNR-RDNA3](https://github.com/mauri870/DLSSNR-RDNA3), based on mochizuki0323's DLSSNR-AMD). This project is not affiliated with, endorsed by or supported by NVIDIA or AMD. DLSS is a trademark of NVIDIA Corporation. No NVIDIA files or network weights are in this repository.
