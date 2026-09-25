// Cross-compile-only ABI check. No main, board services, keys or deployment.
#include "characterization_capture.h"
#include "characterization_evidence.h"
struct CompileCrypto {
 bool sha256(const uint8_t*,size_t,uint8_t (&)[32]);
 bool hmac_sha256(const uint8_t (&)[32],const uint8_t*,size_t,uint8_t (&)[32]);
};
using Session=rocell_diag::CharacterizationSession<CompileCrypto>;
static_assert(sizeof(Session)<32768,"Campaign session exceeds provisional allocation budget");
static_assert(sizeof(rocell_diag::CharacterizationCapture)<2048,"Capture allocation regression");
static_assert(sizeof(rocell_diag::CharacterizationPrepare)<2048,"Preparation allocation regression");
static_assert(sizeof(rocell_diag::CharacterizationEvidence)<24576,"Evidence allocation regression");
