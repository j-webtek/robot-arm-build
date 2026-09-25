// Actual pinned library against host-only serial emulator. No physical UART.
#define main run_hold_wire_cases
#include "test_hold_servo_wire.cpp"
#undef main
#include "held_elbow_leg_owner.h"
bool healthy(void*){return true;}
int main(){using namespace rocell_diag;
  assert(run_hold_wire_cases()==0);
  for(int scenario=0;scenario<6;++scenario){
    HardwareSerial serial;serial.position[3]=2902;serial.goal[3]=2902;serial.torque[3]=1;
    serial.follow_target=scenario!=1;serial.drop_write_ack=scenario==2;
    serial.bad_ack=scenario==3;serial.bad_read_checksum=scenario==4;serial.wrong_read_id=scenario==5;
    SMS_STS library;library.pSerial=&serial;
    HoldInitializationPolicy p;
    for(size_t i=0;i<7;++i){p.minimum[i]=serial.position[i]-16;p.maximum[i]=serial.position[i]+16;}
    Clock clock;HeldElbowLegOwner forward(p,2908,2,healthy);
    for(int i=0;i<30;++i){clock.tick+=110000;forward.poll(library,clock);}
    assert(forward.phase()==(scenario==0?HeldLegPhase::Arrived:
        scenario==1?HeldLegPhase::NotArrived:HeldLegPhase::Fault));
    assert(serial.writes==unsigned(scenario>=4?0:1));
    const auto packet_count=serial.packets.size();
    forward.poll(library,clock);assert(serial.packets.size()==packet_count);
    for(const auto& packet:serial.packets){
      assert(packet[4]==2||packet[4]==3); // No broadcast, torque, mode, reset writes.
      if(packet[4]!=3)continue;
      const auto* a=forward.action();assert(a&&packet[2]==14&&packet[5]==41&&packet.size()==14);
      assert(std::memcmp(packet.data()+6,a->bytes,7)==0);
      assert(packet[7]==(2908&255)&&packet[8]==(2908>>8));
      assert(packet[6]==1&&packet[9]==0&&packet[10]==0&&packet[11]==20&&packet[12]==0);
    }
    if(scenario==2||scenario==3){
      assert(serial.position[3]==2908); // Device acted despite lost/corrupt ACK.
      assert(forward.action()->ack.status!=DispatchStatus::Succeeded);
    }
    if(scenario==0){
      HeldElbowLegOwner reverse(p,2902,2,healthy);
      for(int i=0;i<30;++i){clock.tick+=110000;reverse.poll(library,clock);}
      assert(reverse.phase()==HeldLegPhase::Arrived&&serial.writes==2);
      assert(serial.position[3]==2902&&serial.goal[3]==2902);
      size_t writes=0;
      for(const auto& packet:serial.packets){if(packet[4]!=3)continue;
        const auto* a=writes++?reverse.action():forward.action();
        assert(packet[2]==14&&packet[5]==41&&std::memcmp(packet.data()+6,a->bytes,7)==0);
      }
      assert(writes==2);
    }
  }
  return 0;
}
