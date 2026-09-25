"""Native reviewed-hover table matches the offline Python manifest."""
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.reviewed_hover_manifest import POSES,ghost_key_manifest,validate_manifest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    source = r'''
#include "reviewed_hover_manifest.h"
#include <cstdio>
#include <cstdlib>
using rocell_diag::ReviewedHoverManifest;
int main(int argc,char** argv) {
  uint8_t ids[ReviewedHoverManifest::max_legs+1]{};
  if(argc<2) return 2;
  for(int i=1;i<argc;++i) {
    const long value=std::strtol(argv[i],nullptr,10);
    if(value<0||value>255) return 3;
    ids[i-1]=uint8_t(value);
  }
  if(ReviewedHoverManifest::validate(ids,size_t(argc-1))) {
    for(int i=1;i<argc;++i) {
      const auto* goal=ReviewedHoverManifest::goals[ids[i-1]];
      for(int j=0;j<7;++j) std::printf("%u%c",unsigned(goal[j]),j==6?'\n':',');
    }
    return 0;
  }
  return 1;
}
'''
    target = tmp_path_factory.mktemp("reviewed-hover-native")/"manifest.exe"
    result = subprocess.run([compiler,"-std=c++17","-O2","-x","c++","-",
        "-I"+str(ROOT/"firmware/diagnostics"),"-o",str(target)],
        input=source,capture_output=True,text=True)
    assert result.returncode == 0,result.stderr
    return target


IDS = {"A_CLEAR":0,"A_HOVER":1,"A_DOWN":2,
       "B_CLEAR":3,"B_HOVER":4,"B_DOWN":5}


def test_native_accepts_exact_python_ghost_sequence(native):
    manifest = ghost_key_manifest()
    expected = validate_manifest(manifest)
    result = subprocess.run([str(native),*[str(IDS[name]) for name in manifest["pose_ids"]]],
                            capture_output=True,text=True,timeout=5)
    assert result.returncode == 0,result.stderr
    observed = [[int(value) for value in row.split(",")]
                for row in result.stdout.splitlines()]
    assert observed == expected["targets"]
    assert observed == [list(POSES[name]) for name in manifest["pose_ids"]]


@pytest.mark.parametrize("ids",[
    [],[5],[1,1],[1,2,1,0,4,5,4,3]*2+[1],
    [1,2,1,0,6],[1,2,0],[4,2],[0],
])
def test_native_rejects_unreviewed_or_unbounded_sequences(native,ids):
    result = subprocess.run([str(native),*[str(value) for value in ids]],
                            capture_output=True,text=True,timeout=5)
    assert result.returncode != 0
