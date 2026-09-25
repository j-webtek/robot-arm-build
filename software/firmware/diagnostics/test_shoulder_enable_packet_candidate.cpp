// Compile against the actual retained SCS.cpp, with a memory-only transport.
#include <cassert>
#include <vector>
#include <iostream>
#include "SCS.h"
#include "shoulder_enable_packet_candidate.h"
class MemoryBus:public SCS {
 public:
  std::vector<unsigned char> bytes;int reads=0,flushes=0;
  int writeSCS(unsigned char* data,int count) override {
    bytes.insert(bytes.end(),data,data+count);return count;
  }
  int writeSCS(unsigned char byte) override {bytes.push_back(byte);return 1;}
  int readSCS(unsigned char*,int) override {++reads;return 0;}
  void rFlushSCS() override {}
  void wFlushSCS() override {++flushes;}
};
int main(){
  MemoryBus bus;rocell_diag::ShoulderEnablePacketCandidate candidate;
  assert(candidate.emit_once(bus)==rocell_diag::ShoulderEnableDelivery::SentUnacknowledged);
  const std::vector<unsigned char> expected={0xff,0xff,0xfe,8,0x83,40,1,12,1,13,1,0x32};
  assert(bus.bytes==expected);assert(bus.reads==0);assert(bus.flushes==1);
  assert(candidate.emit_once(bus)==rocell_diag::ShoulderEnableDelivery::NotAttempted);
  assert(bus.bytes==expected);assert(bus.flushes==1);
  std::cout<<"SHOULDER_ENABLE_WIRE_MODEL_PASSED; NO_HARDWARE; NO_ACK_PROOF\n";
}
