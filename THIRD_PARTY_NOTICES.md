# Tactevra third-party notices

**Document status:** Current attribution index

**Authority:** Informational inventory only. Upstream terms govern; this page is
not legal advice, a complete software bill of materials, or a redistribution
grant.

The repository [Apache-2.0 license](LICENSE) applies only to original Tactevra
contributions. Third-party software, models, drawings, firmware, and other
materials retain their own terms. A package name or link below does not mean
that its files are bundled with a Tactevra source archive.

## Direct software dependencies

The maintained Python dependency contract is
[`software/pyproject.toml`](software/pyproject.toml). Its direct requirements
currently include:

- [Pillow](https://python-pillow.github.io/),
  [packaging](https://packaging.pypa.io/), and
  [setuptools](https://setuptools.pypa.io/);
- optional [pySerial](https://pyserial.readthedocs.io/) transport support;
- optional [NumPy](https://numpy.org/) and
  [OpenCV](https://opencv.org/) vision/calibration support; and
- [pytest](https://pytest.org/) and
  [jsonschema](https://python-jsonschema.readthedocs.io/) development support.

The RC02 and RC03 hardware workspaces also declare CAD, reporting, and vision
tools in their `requirements-cad.txt` and `requirements-vision.txt` files,
including CadQuery, trimesh, ezdxf, svgwrite, ReportLab, Matplotlib, Mistune,
Beautiful Soup, WeasyPrint, NumPy, Pillow, and OpenCV. These manifests request
installations from their upstream distributions; they do not copy those
packages into this repository.

Resolved environments contain transitive dependencies that are not enumerated
here. Before publishing a binary, installer, container, or other bundled
distribution, capture its exact resolved dependency set and review the license
and notice obligations for every included version.

## Waveshare RoArm-M3 sources

The [pinned arm-model record](software/models/roarm_m3/README.md) identifies the
exact Waveshare ROS workspace, Python SDK, firmware, STEP, and drawing revisions
used as engineering references.

- The local
  [`roarm_m3_kinematic_40dbd84.urdf`](software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf)
  is a reduced projection derived from the official
  [`waveshareteam/roarm_ws`](https://github.com/waveshareteam/roarm_ws) Xacro.
  The upstream `roarm_description/package.xml` explicitly declares `MIT`. The
  pinned tree supplies no applicable complete MIT license text or copyright
  notice, the Xacro has no license header, and GitHub's repository-license
  endpoint does not identify a repository license. Tactevra therefore records
  this as **upstream-declared MIT; complete notice and scope unconfirmed**. The
  repository-owner disposition, caveats, exact identities, and reconsideration
  triggers are preserved in
  [decision 0001](docs/decisions/0001-waveshare-model-license-disposition.md).
  This is not a claim that Tactevra owns or relicenses the vendor material.
- The referenced
  [`waveshare_roarm_sdk`](https://github.com/waveshareteam/waveshare_roarm_sdk)
  repository identifies its license as AGPL-3.0. Tactevra links to and compares
  the SDK but does not vendor its source in this repository.
- Official firmware archives, assembly geometry, and drawings are recorded by
  URL and digest for traceability. Their inclusion in an engineering record is
  not permission to redistribute the referenced bytes.

## AI model candidates

Model names and terms are recorded in the applicable candidate manifests and
training documentation under [`software/ai/train/`](software/ai/train/).
External Llama, Gemma, Qwen, and other model artifacts are not relicensed by
Tactevra. The source-only repository does not intentionally include trained
model weights, local Ollama storage, private inputs, or raw training runs.

Anyone distributing a model or adapter must review the exact base-model terms,
adapter/data provenance, acceptable-use obligations, and required notices for
that artifact. A local experiment or manifest entry is not release approval.

## Vendor geometry and media

The Arducam B0477 STEP reference is link-only. Its URL, digest, and unresolved
file-specific redistribution status are documented in the
[`vendor` record](hardware/static_overhead_camera/vendor/README.md); the vendor
STEP bytes are intentionally excluded.

Other product names, trademarks, screenshots, and externally sourced media
remain the property of their respective owners. Descriptive reference does not
imply endorsement or transfer of rights.

## Maintainer review

For every proposed release or new bundled artifact:

1. compare this index with all active manifests and newly tracked derived or
   copied materials;
2. preserve upstream copyright, license, attribution, and notice files;
3. verify exact selected versions and transitive dependencies rather than
   relying only on version ranges;
4. resolve every unknown or incompatible redistribution term before publishing;
   and
5. record any intentionally external artifact by source, immutable identity,
   digest, and retrieval terms without committing private or restricted bytes.

The absence of a material from this index is not evidence that it is
first-party, unrestricted, or safe to redistribute. Report an omission through
the normal [contribution workflow](CONTRIBUTING.md); report sensitive licensing
or provenance concerns through the [private security channel](SECURITY.md).
