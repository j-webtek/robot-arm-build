// Uses the actual pinned SMS_STS -> SCS -> SCSerial implementation with a fake
// HardwareSerial sink. Proves software encoding/parsing, not physical UART I/O.
#include <cassert>
#include <cstring>
#include "SMS_STS.h"
#include "hold_initialization_owner.h"
unsigned long millis(){static unsigned long tick=0;return ++tick;}
int HardwareSerial::read(){if(incoming.empty())return -1;int value=incoming.front();incoming.pop_front();return value;}
size_t HardwareSerial::write(const unsigned char* data,size_t count){
  for(size_t i=0;i<count;++i){
    pending.push_back(data[i]);
    if(pending.size()>=4&&pending.size()==size_t(pending[3])+4){respond();pending.clear();}
  }
  return count;
}
void HardwareSerial::respond(){
  packets.push_back(pending);
  assert(pending[0]==255&&pending[1]==255);
  uint8_t sum=0;for(size_t i=2;i<pending.size();++i)sum+=pending[i];assert(sum==255);
  const unsigned id=pending[2],inst=pending[4],addr=pending[5];assert(id>=11&&id<=17);
  const auto index=id-11;std::vector<uint8_t> payload;
  if(inst==2){
    assert(pending.size()==8);payload.resize(pending[6],0);
    if(addr==42){assert(payload.size()==2);payload[0]=goal[index]&255;payload[1]=goal[index]>>8;}
    else if(addr==56){assert(payload.size()==15);payload[0]=position[index]&255;payload[1]=position[index]>>8;}
    else if(addr==40){assert(payload.size()==1);payload[0]=torque[index];}
    else assert(addr==33&&payload.size()==1);
  }else{
    assert(inst==3&&id==14);++writes;
    if(addr==41){assert(pending.size()==14);goal[index]=pending[7]|(unsigned(pending[8])<<8);
      if(follow_target)position[index]=goal[index];
      if(automatic)torque[index]=1;}
    else {assert(addr==40&&pending.size()==8&&pending[6]==1);torque[index]=1;}
    if(drop_write_ack)return; // Execute but lose the response: never resend.
  }
  std::vector<uint8_t> response={255,255,uint8_t(id),uint8_t(payload.size()+2),0};
  if(inst==2&&wrong_read_id)response[2]=uint8_t(id+1);
  response.insert(response.end(),payload.begin(),payload.end());sum=0;
  for(size_t i=2;i<response.size();++i)sum+=response[i];
  response.push_back(uint8_t(~sum));
  if(inst==3&&bad_ack)response.back()^=1;
  if(inst==2&&bad_read_checksum)response.back()^=1;
  for(auto byte:response)incoming.push_back(byte);
}
struct Clock {uint64_t tick=100;uint64_t now_us(){return ++tick;}};
int main(){using namespace rocell_diag;
  for(int scenario=0;scenario<5;++scenario){
    HardwareSerial serial;serial.automatic=scenario!=1;
    serial.drop_write_ack=scenario==2;serial.bad_ack=scenario==3;
    if(scenario==4){serial.automatic=false;serial.torque[3]=1;serial.goal[3]=2724;}
    SMS_STS library;library.pSerial=&serial;
    HoldInitializationPolicy p;p.permit_explicit_enable=scenario==1;
    for(size_t i=0;i<7;++i){p.minimum[i]=serial.position[i]-8;p.maximum[i]=serial.position[i]+8;}
    HoldInitializationOwner owner(p);Clock clock;
    for(int step=0;step<10;++step){clock.tick+=110000;owner.poll(library,clock);}
    assert(owner.phase()==(scenario<2||scenario==4?HoldPhase::Captured:HoldPhase::Fault));
    assert(serial.writes==unsigned(scenario==1?2:1));
    size_t action=0;
    for(const auto& packet:serial.packets){if(packet[4]!=3)continue;
      const auto* evidence=owner.action(action++);assert(evidence);
      assert(packet[2]==evidence->servo_id&&packet[5]==evidence->address);
      assert(packet.size()==size_t(evidence->width)+7);
      assert(std::memcmp(packet.data()+6,evidence->bytes,evidence->width)==0);
    }
    assert(action==owner.action_count());
    assert(serial.goal[3]==2723&&serial.torque[3]==1);
    if(scenario==2||scenario==3)assert(owner.action(0)->ack.status!=DispatchStatus::Succeeded);
  }
  return 0;
}
