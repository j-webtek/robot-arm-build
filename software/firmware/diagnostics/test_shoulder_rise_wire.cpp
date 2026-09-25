// Actual retained SMS_STS/SCS/SCSerial encoding, memory-only serial sink.
#include <cassert>
#include "SMS_STS.h"
unsigned long millis(){static unsigned long value=0;return ++value;}
int HardwareSerial::read(){return -1;}
size_t HardwareSerial::write(const unsigned char* data,size_t count){
  for(size_t i=0;i<count;++i){
    pending.push_back(data[i]);
    if(pending.size()>=4&&pending.size()==size_t(pending[3])+4){respond();pending.clear();}
  }
  return count;
}
void HardwareSerial::respond(){packets.push_back(pending);}
int main(){
  HardwareSerial serial;SMS_STS library;library.pSerial=&serial;assert(library.End==0);
  uint8_t ids[2]={12,13},acc[2]={1,1};uint16_t speeds[2]={20,20};int16_t targets[2]={2443,1671};
  library.SyncWritePosEx(ids,2,targets,speeds,acc);
  std::vector<uint8_t> expected={255,255,254,20,0x83,41,7,
      12,1,0x8b,0x09,0,0,20,0,13,1,0x87,0x06,0,0,20,0};
  uint8_t sum=0;for(size_t i=2;i<expected.size();++i)sum+=expected[i];expected.push_back(uint8_t(~sum));
  assert(serial.packets.size()==1&&serial.packets[0]==expected);
  assert(targets[0]==2443&&targets[1]==1671);
  return 0;
}
