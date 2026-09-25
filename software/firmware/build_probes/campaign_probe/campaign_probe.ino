// COMPILE PROBE ONLY. Never flash as robot firmware. setup/loop do nothing.
#include <Arduino.h>
#include <WebServer.h>
#include <SCServo.h>
#include "start_crypto_esp32.h"
#include "characterization_composition.h"
#include "characterization_evidence.h"
struct ProbeClock{uint64_t now_us(){return esp_timer_get_time();}};
struct ProbeServices {
  SMS_STS& servo;ProbeClock& timer;rocell_diag::CharacterizationEvidence& evidence;
  bool healthy(){return false;}bool reserve(){return false;}bool owned(){return false;}
  bool memory_fits(size_t bytes,size_t reserve){return ESP.getFreeHeap()>=bytes+reserve&&ESP.getMaxAllocHeap()>=bytes;}
  auto& clock(){return timer;}auto& bus(){return servo;}
  bool entropy(uint8_t* bytes,size_t size){esp_fill_random(bytes,size);return true;}
  bool load_key(uint8_t (&)[32]){return false;}bool boot(uint8_t (&)[16]){return false;}
  bool retain(const char* event,unsigned leg,const rocell_diag::ShoulderPreloadPose& pose,const rocell_diag::CharacterizationResult* result){return evidence(event,leg,pose,result);}
  bool release_evidence(unsigned completed){return evidence.release_after_receipt(completed);}
};
using App=rocell_diag::CharacterizationComposition<rocell_diag::Esp32StartCrypto,ProbeServices,ProbeClock,WebServer>;
static_assert(sizeof(App)<8192,"Composition allocation budget");
static_assert(sizeof(rocell_diag::CharacterizationEvidence)<24576,"Evidence allocation budget");
// Force template compilation with real WebServer, SCServo and ESP32 crypto.
// Never called; linker may remove it, so sketch flash/RAM totals are NOT a
// complete campaign-runtime resource measurement.
void compileIntegration(App& app){app.register_routes();app.poll();}
void setup(){}
void loop(){}
