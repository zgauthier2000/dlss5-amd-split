#!/usr/bin/env python3
"""Build the Linux network for one GPU architecture from linux/shaders/<arch>/pipelines.json.

    build_network.py <arch> [--int4 | --performance | --ultra | --optimized | --experimental | --expint4] [--x2] [--out DIR] [--check DIR]

Writes (default build/linux/<arch>/network, with --int4 build/linux/<arch>/network-int4, with --performance
build/linux/<arch>/network-performance, with --optimized
build/linux/<arch>/network-optimized, with --experimental build/linux/<arch>/network-experimental):
    g_<name>.spv + the four marker files   the network, what --spv-dir points at
    runtime/                                 the arch-neutral passes (linux/shaders/passes)
    g_<name>_grade.spv                      style_grade: the post block with the Natural/Cinematic grade
    temporal/                                the temporal variants (+ their _grade twins) and the motion estimator

The host must be compiled with the same constants: linux/build/arch/<arch>.sh.
--optimized: CC_SILVER_AARDWOLD_OPTIMIZED (pipelines.json with pipelines-optimized.json applied; the same host).
--int4: CC_SILVER_AARDWOLD_OPTIMIZED with its int4 layers (pipelines.json with pipelines-int4.json applied; the host
built with NR_INT4=1); also the host's g_<name>.spv.iu4 markers and hs-pipelines.txt (the pipelines built with the
hard-swish, for the host's guard).
--performance / --ultra: CC_SILVER_AARDWOLD_OPTIMIZED at Optimized layers Performance / Ultra Performance
(pipelines-performance.json / pipelines-ultra.json; as --int4; out network-performance / network-ultra).
--experimental: CC_SMALL_FP8_EXPERIMENTAL (pipelines.json with pipelines-experimental.json applied; the same host).
Each of the three: the network and temporal/ (the runtime passes are the default network's), fixed-attention.txt (the
pipelines whose fixed probability tables the host writes), and when the overlay says so const-heads.txt (the host
proves and marks the constant C=512 attention heads, NR_CONSTH) and block-routes.txt (blocks whose layers run on a
pipeline of their own: "<suffix> <kernel>... : <block>...", from the overlay's "routes").
--expint4 (ours): CC_SMALL_FP8_EXPERIMENTAL with the legacy int4 ViT / attention routes (pipelines-expint4.json; host
NR_INT4=1, [Network] ExperimentalInt4 = 1): as --experimental plus the .iu4 markers and hs-pipelines.txt.
--x2 (ours): FP8 rounding mix X2 (NR_QUANT_F16_ONLY=1 on X2_STEMS: those layers keep FP16 activations), the
experimental/shaders-x2 folders ([Network] FP16Activations = 1).
Always (ours): NR_MID_FUSE=1 on the six persistent expand/reduce pipelines (spill fix; byte-identical output).
--check DIR compares every network SPV and marker with DIR byte for byte and
lists the differences (exit 1 if any).
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
# the runtime's own passes around the network (it runs the network only: the composition is RenoDX's stage's and the
# wilsjo2 flow's): the alpha restore and the depth guide's copy
RUNTIME = ['runtime_alpha', 'runtime_depth', 'runtime_blit',
           'runtime_reuse_store', 'runtime_reuse_motion', 'runtime_reuse_warp', 'runtime_reuse_stat',
           'runtime_reuse_motion3', 'runtime_reuse_warp3', 'runtime_reuse_stat3',
           'runtime_reuse_warp4', 'runtime_reuse_cut',
           'runtime_reuse_warp5', 'runtime_reuse_snap_prep', 'runtime_reuse_snap_box', 'runtime_reuse_snap_apply',
           'runtime_reuse_stat_max', 'runtime_reuse_stat_accg', 'runtime_reuse_stat3g',
           'runtime_reuse_cut_terms', 'runtime_reuse_cut_sum', 'runtime_reuse_moved_prep', 'runtime_reuse_store_ema']
# the answer-into-the-frame twins (NR_ANSWER16=1), loaded as <name>_a16.spv
RUNTIME_A16 = ['runtime_reuse_warp4', 'runtime_reuse_warp5', 'runtime_reuse_snap_apply']
MOTION = ['motion_luma', 'motion_estimate']
# spill fix (dlssnr/spill): each expand group's quantized fragment feeds the middle MMAs at once
MID_FUSE = {'g_fswinpds64', 'g_fswinpup64', 'g_fswinpds128', 'g_fswinpup128', 'g_fswinpds256', 'g_fswinpup256'}
# FP8 rounding mix X2 (dlssnr/spill section 12): these outputs keep FP16 activations
X2_STEMS = set('g_fswinimagepost32,g_fswinimagepost32_grade,temporal_post_fp32,temporal_post_fp32hp,temporal_post_fp32h16,'
               'temporal_post_fp32_grade,temporal_post_fp32hp_grade,temporal_post_fp32h16_grade,g_fswinpup64,g_fswinfusedup64,'
               'g_fswinfusedup32,g_fswinfusedup32nh,g_fswin32nhd,g_decups,g_gemmvqkvs,g_gemmvact,g_gemmvact4,g_gemmvact4c,'
               'g_gemmproj,g_gemmproj4,g_gemmproj4s,g_gemmprojs,g_gemmprojw,g_gemmprojw4,g_gemmprojw4s,g_gemmprojws,g_gemmprojt,'
               'g_gemmvqkvnorms,g_gemmvqkvnorm,g_gemmvqkvnorm4,g_gemmvqkvnorms4,g_gemmvqkv,g_vitattn,g_gemmvnores,g_gemmvproj,'
               'g_fswinpup128,g_fswinfusedup128,g_fswinpup256,g_fswinfusedup256,g_ffwd3w,g_ffwd3,g_attn,g_attn4,g_gemmprojc,'
               'g_gemmprojcs,g_gemmpool,g_gemmnores,g_fswinpds256,g_fswin256,g_fswinds256,g_fswindsp256,g_fswinp256'.split(','))
X2 = False


def glslang(arch, src, defines, out):
    cmd = [str(R / 'toolchain/glslang/bin/glslang'), '-V', '--target-env', 'vulkan1.3',
           '-I' + str(R / 'linux/shaders' / arch / 'include'), '-I' + str(R / 'linux/shaders/passes/include')]
    extra = ['NR_QUANT_F16_ONLY=1'] if X2 and out.stem in X2_STEMS else []
    if out.stem in MID_FUSE:
        extra = extra + ['NR_MID_FUSE=1']
    cmd += ['-D' + d for d in list(defines) + extra] + [str(src), '-o', str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'glslang failed on {src}:\n{r.stdout}{r.stderr}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('arch')
    ap.add_argument('--int4', action='store_true')
    ap.add_argument('--legacy-int4', action='store_true', help='RDNA3 legacy network for unchanged golden checks')
    ap.add_argument('--performance', action='store_true')
    ap.add_argument('--ultra', action='store_true')
    ap.add_argument('--optimized', action='store_true')
    ap.add_argument('--experimental', action='store_true')
    ap.add_argument('--expint4', action='store_true')
    ap.add_argument('--x2', action='store_true')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--check', type=Path)
    a = ap.parse_args()
    table = json.loads((R / 'linux/shaders' / a.arch / 'pipelines.json').read_text())
    if a.legacy_int4 + a.int4 + a.performance + a.ultra + a.optimized + a.experimental + a.expint4 > 1:
        sys.exit('one of --int4, --performance, --ultra, --optimized, --experimental, --expint4')
    global X2
    X2 = a.x2
    overlay = ('int4-legacy' if a.legacy_int4 else 'int4' if a.int4 else 'performance' if a.performance else 'ultra' if a.ultra else 'optimized' if a.optimized
               else 'experimental' if a.experimental else 'expint4' if a.expint4 else '')
    if overlay:
        i4 = json.loads((R / 'linux/shaders' / a.arch / f'pipelines-{overlay}.json').read_text())
        default = table['pipelines']
        def derive(e, c):
            return dict(e, defines=[x for x in e['defines'] if x not in c.get('remove', [])] + c.get('add', []))
        assert not set(i4['change']) - set(default), 'pipelines-%s.json changes unknown pipelines' % overlay
        table['pipelines'] = {k: derive(e, i4['change'].get(k, {})) for k, e in default.items()}
        table['pipelines'].update({k: derive(default[c['base']], c) for k, c in i4['new'].items()})
    out = a.out or R / 'build/linux' / a.arch / ((f'network-{overlay}' if overlay else 'network') + ('-x2' if a.x2 else ''))
    if out.exists():
        shutil.rmtree(out)
    (out / 'runtime').mkdir(parents=True)
    (out / 'temporal').mkdir()

    pipelines = table['pipelines']
    # post_no_out1 in the manifest tells the host that the post kernels never write their second output (it makes
    # that image 1x1): it has to say what they are built with.
    consts = dict(r.split() for r in table['markers']['shader-constants.txt'][1:])
    if consts.get('post_no_out1') == '1' and 'NR_POST_NO_OUT1=1' not in pipelines['fswinimagepost32']['defines']:
        sys.exit('pipelines.json: post_no_out1 1, but fswinimagepost32 is built without NR_POST_NO_OUT1=1')
    for name, e in pipelines.items():
        glslang(a.arch, R / 'linux/shaders' / a.arch / e['source'], e['defines'], out / f'g_{name}.spv')
    for name, text in table['markers'].items():
        (out / name).write_text('\n'.join(text) + '\n' if isinstance(text, list) else text + '\n')
    for name, v in table['variants'].items():
        base = pipelines[v['base']]
        glslang(a.arch, R / 'linux/shaders' / a.arch / base['source'], base['defines'] + v['add'],
                out / 'temporal' / f'{name}.spv')
    # RDNA3's network has no Style grade pipelines: the runtime runs the plain post block without them
    grade = table.get('style_grade', {'pipelines': [], 'variants': [], 'add': []})
    for name in grade['pipelines']:
        e = pipelines[name]
        glslang(a.arch, R / 'linux/shaders' / a.arch / e['source'], e['defines'] + grade['add'], out / f'g_{name}_grade.spv')
    for name in grade['variants']:
        base = pipelines[table['variants'][name]['base']]
        glslang(a.arch, R / 'linux/shaders' / a.arch / base['source'],
                base['defines'] + table['variants'][name]['add'] + grade['add'], out / 'temporal' / f'{name}_grade.spv')
    for k in MOTION:
        glslang(a.arch, R / 'linux/shaders/passes' / f'{k}.comp', [], out / 'temporal' / f'{k}.spv')
    shutil.copy2(out / 'shader-constants.txt', out / 'temporal' / 'shader-constants.txt')
    if a.legacy_int4 or a.int4 or a.performance or a.ultra or a.expint4:
        for name in i4['iu4']:
            (out / f'g_{name}.spv.iu4').write_text('0\n')
        hs = sorted(k for k, e in pipelines.items() if 'NR_ACT_HS=2' in e['defines'])
        (out / 'hs-pipelines.txt').write_text('\n'.join(hs) + '\n')
    if overlay:
        fixp = sorted(k for k, e in pipelines.items() if 'NR_FIXP=1' in e['defines'])
        (out / 'fixed-attention.txt').write_text('\n'.join(fixp) + '\n')
        consth = sorted(k for k, e in pipelines.items() if 'NR_CONSTH=1' in e['defines'])
        if consth:
            (out / 'const-heads.txt').write_text('\n'.join(consth) + '\n')
        if i4.get('routes'):
            lines = []
            for r in i4['routes']:
                assert all(f'{k}{r["suffix"]}' in pipelines for k in r['kernels']), r
                lines.append(' '.join([r['suffix']] + r['kernels'] + [':'] + [str(b) for b in r['blocks']]))
            (out / 'block-routes.txt').write_text('\n'.join(lines) + '\n')
        (out / 'runtime').rmdir()
    else:
        for k in RUNTIME:
            glslang(a.arch, R / 'linux/shaders/passes' / f'{k}.comp', [], out / 'runtime' / f'{k}.spv')
        for k in RUNTIME_A16:
            glslang(a.arch, R / 'linux/shaders/passes' / f'{k}.comp', ['NR_ANSWER16=1'], out / 'runtime' / f'{k}_a16.spv')
    print(f'{out}: {len(pipelines) + len(grade["pipelines"])} network pipelines, '
          f'{len(table["variants"]) + len(grade["variants"]) + len(MOTION)} temporal, '
          f'{0 if overlay else len(RUNTIME)} runtime')

    if a.check:
        bad = [p.name for p in sorted(out.iterdir()) if p.is_file()
               if not (a.check / p.name).is_file() or (a.check / p.name).read_bytes() != p.read_bytes()]
        print('check against', a.check, ':', 'identical' if not bad else 'DIFFERENT: ' + ' '.join(bad))
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
