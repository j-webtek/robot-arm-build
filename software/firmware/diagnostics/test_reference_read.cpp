// Link against the pinned vendor SCS.cpp; all transport is an in-memory packet.
#include "SCS.h"
#include <stdio.h>
#include <assert.h>
#include "reference_read_adapter.h"

class PacketBus : public SCS {
 public:
  unsigned char packet[21]={}; int cursor=0; int available=8; int writes=0;
  PacketBus(unsigned char id,unsigned char length,unsigned char width=2) : SCS(0,1) {
    assert(width==2 || width==15);available=width+6;
    packet[0]=255;packet[1]=255;packet[2]=id;packet[3]=length;
    packet[4]=0;packet[5]=0x34;packet[6]=0x08;
    packet[width+5]=static_cast<unsigned char>(~(id+length+packet[4]+packet[5]+packet[6]));
  }
 protected:
  int writeSCS(unsigned char*,int count) override { ++writes;return count; }
  int writeSCS(unsigned char) override { ++writes;return 1; }
  int readSCS(unsigned char* output,int count) override {
    int copied=0;
    while (copied<count && cursor<available) output[copied++]=packet[cursor++];
    return copied;
  }
  void rFlushSCS() override {}
  void wFlushSCS() override {}
};

int main() {
  unsigned char bytes[2]={};
  PacketBus correct(14,4),wrong_id(15,4),wrong_length(14,5);
  const int good=correct.Read(14,42,bytes,2);
  const int foreign=wrong_id.Read(14,42,bytes,2);
  const int malformed=wrong_length.Read(14,42,bytes,2);
  assert(good==2);
  int truncations=0;
  for (int size=0;size<8;++size) {
    PacketBus cut(14,4);cut.available=size;
    assert(cut.Read(14,42,bytes,2)==0);++truncations;
  }
  PacketBus bad_checksum(14,4);bad_checksum.packet[7]^=1;
  assert(bad_checksum.Read(14,42,bytes,2)==0);
  PacketBus stale_error(14,4);stale_error.Error=32;stale_error.available=0;
  assert(stale_error.Read(14,42,bytes,2)==0 && stale_error.Error==32);
  // Recovery is a separate explicit request with a new available packet, not an
  // automatic retry or proof of native serial-buffer resynchronization.
  stale_error.available=8;stale_error.cursor=0;
  assert(stale_error.Read(14,42,bytes,2)==2 && stale_error.Error==0);
  int adapter_cases=0;
#ifdef ROCELL_VALIDATE_RESPONSE
  assert(foreign==0 && malformed==0);
  PacketBus adapter_bus(14,4);
  rocell_diag::ReferenceReadAdapter<PacketBus> adapter(adapter_bus);
  auto read=adapter.read(14,42,2,bytes);
  assert(read.returned_bytes==2 && read.device_error==0 && bytes[0]==0x34);++adapter_cases;
  adapter_bus.available=0;adapter_bus.cursor=0;adapter_bus.Error=32;
  read=adapter.read(14,42,2,bytes);
  assert(read.returned_bytes==0 && read.device_error==-1 && bytes[0]==0);++adapter_cases;
  PacketBus wrong_adapter_bus(15,4);
  rocell_diag::ReferenceReadAdapter<PacketBus> wrong_adapter(wrong_adapter_bus);
  read=wrong_adapter.read(14,42,2,bytes);
  assert(read.returned_bytes==0 && read.device_error==-1);++adapter_cases;
  const int before=adapter_bus.writes;
  read=adapter.read(254,42,2,bytes);
  assert(read.returned_bytes==0 && adapter_bus.writes==before);++adapter_cases;
  read=adapter.read(14,33,1,bytes);
  assert(read.returned_bytes==0 && adapter_bus.writes==before);++adapter_cases;
  PacketBus servo_error(14,4);servo_error.packet[4]=32;
  servo_error.packet[7]=static_cast<unsigned char>(~(14+4+32+0x34+0x08));
  rocell_diag::ReferenceReadAdapter<PacketBus> error_adapter(servo_error);
  read=error_adapter.read(14,42,2,bytes);
  assert(read.returned_bytes==2 && read.device_error==32 && bytes[0]==0);++adapter_cases;
  PacketBus block_bus(14,17,15);unsigned char block[15]={};
  rocell_diag::ReferenceReadAdapter<PacketBus> block_adapter(block_bus);
  read=block_adapter.read(14,56,15,block);
  assert(read.returned_bytes==15 && read.device_error==0 && block[0]==0x34);++adapter_cases;
#else
  assert(foreign==2 && malformed==2);
#endif
  printf("{\"correct_packet_bytes\":%d,\"wrong_servo_bytes\":%d,\"wrong_length_bytes\":%d,"
      "\"truncation_cases\":%d,\"checksum_failure_rejected\":true,"
      "\"stale_error_reproduced\":true,\"explicit_later_read_recovered\":true,"
      "\"adapter_cases\":%d}\n",good,foreign,malformed,truncations,adapter_cases);
}
