# DLSSNR-AMD split preview (0.0.9-split.1)

An unofficial, experimental build of [DLSSNR-AMD](https://github.com/TheAutomatic/DLSSNR-AMD) 0.0.9 for
**RDNA3 on Linux (Proton)**, adding a frame-rate mode: the NR network runs once every few frames, and that one run is
spread evenly across those frames. This is a preview to show the work and to support a proposal upstream. It is not
an official DLSSNR-AMD release; please report problems with this build here, not to the DLSSNR-AMD project.

Comparison sliders: https://zgauthier2000.github.io/dlss5-amd-split/

## What is added

- **Every N** (`[Reuse] Every`): the network runs once every N frames. Frames in between get the last edit carried
  forward along the game's motion vectors. This builds on the temporal reuse in mauri870's
  [DLSSNR-RDNA3](https://github.com/mauri870/DLSSNR-RDNA3).
- **Split** (`[Reuse] Split = 1`): the one network run is divided into N parts, one per frame, so every frame costs
  about the same. Without it, one frame in N pays the whole network and misses refreshes.
- **Phase** (`[Reuse] Phase = 1`): lines the parts up with an upscaler that skips work on alternate frames. Harmless
  otherwise.
- **Live switching:** NR Control (End key) > Network > Reuse (frame rate): change Every and Split while the game runs.
- **Fixes for carried frames:** fill for revealed background behind moving objects (`Disocclusion`, `DisoccFill`,
  `DisoccFillRim`, `DisoccMotion`), dropping the carried edit at the frame's edges and at scene cuts (`EdgeDrop`, `CutDrop`, `CutChange`), keeping
  a moving character's edit on it (`Snap`, off by default), fading carried darkening where the pixel got darker since capture (`Relit`), steadier history (`HistoryGate`,
  `Blend`), and a halo limit.
- **RDNA3 speed work:** the experimental small model (`CC_SMALL_FP8_EXPERIMENTAL`) on RDNA3, INT4 on it
  (`ExperimentalInt4 = 1`), an FP8 rounding mix with FP16 activations (`[Network] FP16Activations = 1`), and a
  register-spill fix (output byte-identical).
- **Defaults:** 1 pass (`NRPassesMode = legacy`, `NRPasses = 1`), Every 4 + Split + Phase.

Each change was checked against the build before it with its new keys off: same picture byte for byte (md5 per frame).
`[Reuse] Every = 0` turns the frame-rate mode off.

## Measured

RX 7800 XT, Linux, my offline harness (the plugin's runtime over captured game clips), Shadow of the Tomb Raider at
2258 x 1270 with NR at 0.75 scale and 1 pass, one run each:

| | ms per frame, mean | ms per frame, max |
|---|---|---|
| Network every frame | 11.34 | 11.44 |
| Every 4 + Split | 3.60 | 4.09 |

Picture against the every-frame output (PSNR in 8-bit display space, one clip each): Shadow of the Tomb Raider
42.0 dB, Stellar Blade 42.1 dB, Cyberpunk 2077 33.6 dB (fast motion and much revealed background: the weakest case).

Played under Proton in Shadow of the Tomb Raider, Cyberpunk 2077, Stellar Blade demo and Elden Ring.

## Status and limits

- Linux / Proton on RDNA3 (tested on an RX 7800 XT only). RDNA4: not built or tested with these changes.
- Windows: the changes are ported in the source and compile, but have never run on Windows. No Windows package.
- Not tested: the ReShade routes, 32-bit games, the Optimized networks on RDNA3.
- The NVIDIA model is not included. As with DLSSNR-AMD, the installer extracts it from your own `nvngx_dlssnr.dll`.

## Install

Unpack the package and follow `README.txt` in it (DLSSNR-AMD's installer, unchanged in use). For the setup measured
above, choose the experimental network, for example:

    bash install.sh "<game folder>" optiscaler --model CC_SMALL_FP8_EXPERIMENTAL --dll <nvngx_dlssnr.dll or its zip>

### FSR 4 Lite lossy (recommended on RX 7000)

Phase is tuned for FSR 4 Lite lossy, a faster FSR 4.1.2 build for RX 6000 / RX 7000 from
[fsr4-shader-performance-overrides](https://github.com/zgauthier2000/fsr4-shader-performance-overrides). It is not in
this package. Download `fsr4.1.2-cyboman-rx7000-2026-11-22.zip` from its
[dll-2026-11-22 release](https://github.com/zgauthier2000/fsr4-shader-performance-overrides/releases/tag/dll-2026-11-22),
unpack it, read its `WARNING.txt`, and give its `4.1.2l-lossy` file to the installer:

    bash install.sh "<game folder>" optiscaler --model CC_SMALL_FP8_EXPERIMENTAL --dll <nvngx_dlssnr.dll or its zip> \
        --lite <unpacked folder>/4.1.2l-lossy/amd_fidelityfx_upscaler_dx12.dll

The installer puts it in as the DX12 upscaler and sets OptiScaler to use it. The games above were played with the
2026-11-19 build of this file: the 2026-11-22 release is that build byte for byte plus a Windows version of its last
pass, picked when the game starts (under Proton it runs the 2026-11-19 code). The released file itself has not been
run in a game with this plugin. DX12 games only;
not for RX 9000 and never in online games. Without `--lite` the game's upscaling stays OptiScaler's own.

The `[Reuse]` section
of `dlssnr-amd.ini` in the game folder holds the settings above; `Every = 0` turns the frame-rate mode off.

## Credits and license

DLSSNR-AMD by TheAutomatic and contributors; the RDNA3 port by mauri870 (DLSSNR-RDNA3) and its port to 0.0.8.3 by
hedonemaeda, released under the MIT License (its notice: `DLSSNR-AMD-LICENSE.txt`). This build's changes are licensed
under the GNU GPL v2 or later, like [fsr4-shader-performance-overrides](https://github.com/zgauthier2000/fsr4-shader-performance-overrides),
and so is the whole as distributed here (`LICENSE.txt`); v0.0.9-split.1 was published under MIT and stays so. Bundled
third-party parts keep their own licenses (see the package's license files). DLSS is NVIDIA's; this project is not affiliated with NVIDIA or AMD.
