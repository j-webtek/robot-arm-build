// Polled preparation capture. Uses the existing read-only acquisition routine;
// the supplied reservation must exclude every other bus owner until reboot.
#pragma once
#include "characterization_prepare.h"
namespace rocell_diag {
class CharacterizationCapture {
 public:
  template<class Reserve,class Clock> bool begin(Reserve& reserve,Clock& clock){
    if(attempted_)return false;attempted_=true;
    if(!reserve()){failed_=true;return false;}
    started_=last_clock_=clock.now_us();
    if(!started_){failed_=true;return false;}
    active_=true;return true;
  }
  template<class Bus,class Clock,class Admission>
  void poll(Bus& bus,Clock& clock,Admission& admitted){
    if(!active_||failed_||count_==3)return;
    auto now=clock.now_us();
    if(now<last_clock_||now-started_>1500000||!admitted()){failed_=true;return;}
    last_clock_=now;
    if(count_&&now-poses_[count_-1].finished_us<100000)return;
    if(!ShoulderPreloadCandidate::sample(bus,clock,poses_[count_],admitted)){
      failed_=true;return;
    }
    auto finished=clock.now_us();
    if(finished<now||finished-started_>1500000){failed_=true;return;}
    last_clock_=finished;++count_;
  }
  bool copy(rocell_diag::ShoulderPreloadPose (&out)[3])const{
    if(failed_||count_!=3)return false;
    memcpy(out,poses_,sizeof(poses_));return true;
  }
  bool ready()const{return !failed_&&count_==3;}
  bool failed()const{return failed_;}
 private:
  ShoulderPreloadPose poses_[3];unsigned count_=0;
  uint64_t started_=0,last_clock_=0;
  bool attempted_=false,active_=false,failed_=false;
};
}
