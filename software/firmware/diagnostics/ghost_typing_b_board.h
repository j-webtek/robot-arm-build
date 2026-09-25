// Dedicated, manually gated B-key ghost cycle. No generic motion parser.
// Model-only targets: no physical keyboard, stylus or cable clearance sensor.
#pragma once
#include "characterization_board_services.h"
#include <cstdlib>
#include <cstring>

namespace rocell_diag {
class GhostTypingBBoard {
 public:
  using Pose=ShoulderPreloadPose;
  void begin(){
    server.on("/rocell/ghost-b/capabilities",HTTP_GET,[this](){
      char out[256];
      snprintf(out,sizeof(out),
        "{\"schema\":\"rocell.ghost_b.v1\",\"boot_id\":\"%s\","
        "\"maximum_legs\":5,\"automatic_progression\":false,"
        "\"gripper_writes\":false,\"motion_authorized\":false}",
        rocellDiagnosticInstance);
      server.sendHeader("Cache-Control","no-store");
      server.send(200,"application/json",out);
    });
  }
  void poll(){
    while(Serial.available()){
      const char ch=char(Serial.read());
      if(ch=='\n'){
        input_[size_]=0;dispatch(input_);size_=0;
      }else if(ch!='\r'){
        if(size_>=sizeof(input_)-1){size_=0;Serial.println("FAULT:LINE_TOO_LONG");}
        else input_[size_++]=ch;
      }
    }
    if(sent_&&!finished_&&uint32_t(millis()-sent_ms_)>=8000){
      finished_=true;
      Pose after{},check{};
      if(!sample(after)||!sample(check)||!stable(after,check)){
        faulted_=true;Serial.println("FAULT:POST_READ");return;
      }
      const uint16_t* target=goals(next_leg_);
      for(unsigned i=0;i<7;++i){
        if(check.goal[i]!=target[i]||check.torque[i]!=1){
          faulted_=true;Serial.println("FAULT:POST_GOAL");return;
        }
        const bool selected=target[i]!=before_.goal[i];
        const int delta=std::abs(int(check.position[i])-int(
          selected?target[i]:before_.position[i]));
        if(delta>(selected?12:16)){
          faulted_=true;Serial.println("FAULT:POST_POSITION");return;
        }
      }
      verified_=true;sent_=false;++next_leg_;
      Serial.printf("LEG_VERIFIED:%s:%u\n",rocellDiagnosticInstance,next_leg_);
    }
  }
 private:
  static const uint16_t* goals(unsigned index){
    static const uint16_t targets[5][7]={
      {1994,2075,2039,2600,2233,2040,1897}, // B clear
      {1994,2093,2021,2618,2197,2040,1897}, // B hover
      {1994,2105,2009,2630,2173,2040,1897}, // virtual down
      {1994,2093,2021,2618,2197,2040,1897}, // retract
      {1994,2075,2039,2600,2233,2040,1897}, // B clear
    };
    return index<5?targets[index]:nullptr;
  }
  static bool stable(const Pose& a,const Pose& b){
    if(!ShoulderCharacterizationPolicy::valid(a)||
       !ShoulderCharacterizationPolicy::valid(b))return false;
    for(unsigned i=0;i<7;++i){
      if(ShoulderCharacterizationPolicy::moving(a,i)||
         ShoulderCharacterizationPolicy::moving(b,i)||
         std::abs(int(a.position[i])-int(b.position[i]))>8||
         a.goal[i]!=b.goal[i])return false;
    }
    return true;
  }
  bool sample(Pose& pose){
    auto admitted=[](){return st.End==0&&rocellHoldHealthy(nullptr)&&
                              rocellConfigurationBusInactive(nullptr);};
    return FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  bool source(const Pose& pose){
    static const uint16_t initial_goals[7]={2047,2075,2039,2600,2233,2040,1897};
    static const uint16_t initial_positions[7]={2046,2079,2036,2605,2235,2041,1893};
    const uint16_t* expected=next_leg_?goals(next_leg_-1):initial_goals;
    for(unsigned i=0;i<7;++i){
      if(pose.goal[i]!=expected[i]||
         std::abs(int(pose.position[i])-int(next_leg_?expected[i]:initial_positions[i]))>
           (next_leg_?12:16))return false;
    }
    return true;
  }
  void dispatch(const char* line){
    if(std::strcmp(line,"SNAP")==0){
      Pose pose{};
      if(!sample(pose)){Serial.println("FAULT:SNAP_READ");return;}
      snapshot_=pose;snapshot_valid_=true;
      Serial.printf("SNAP:%s:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u:%u\n",
          rocellDiagnosticInstance,
          unsigned(pose.position[0]),unsigned(pose.position[1]),
          unsigned(pose.position[2]),unsigned(pose.position[3]),
          unsigned(pose.position[4]),unsigned(pose.position[5]),
          unsigned(pose.position[6]),unsigned(pose.goal[0]),
          unsigned(pose.goal[1]),unsigned(pose.goal[2]),
          unsigned(pose.goal[3]),unsigned(pose.goal[4]),
          unsigned(pose.goal[5]),unsigned(pose.goal[6]));
      return;
    }
    if(std::strcmp(line,"STATUS")==0){
      Serial.printf("STATUS:%s:%u:%u:%u\n",rocellDiagnosticInstance,
                    next_leg_,unsigned(sent_),unsigned(faulted_));return;
    }
    if(next_leg_>=5||sent_||faulted_||!snapshot_valid_){
      Serial.println("FAULT:NOT_READY");return;
    }
    char expected[48];
    snprintf(expected,sizeof(expected),"LEG:%s:%u",rocellDiagnosticInstance,next_leg_+1);
    if(std::strcmp(line,expected)!=0){Serial.println("FAULT:COMMAND_REJECTED");return;}
    attempted_[next_leg_]=true; // Consume this leg before any fresh bus read.
    Pose fresh{},check{};
    if(!stable(snapshot_,snapshot_)||!source(snapshot_)||
       !sample(fresh)||!stable(snapshot_,fresh)||
       !sample(check)||!stable(fresh,check)||!source(check)){
      faulted_=true;Serial.println("FAULT:PREWRITE_POSE");return;
    }
    const uint16_t* target=goals(next_leg_);
    uint8_t ids[7]{},acc[7]{};int16_t positions[7]{};uint16_t speeds[7]{};
    unsigned count=0;
    for(unsigned i=0;i<7;++i){
      if(target[i]==check.goal[i])continue;
      if(i==6||std::abs(int(target[i])-int(check.goal[i]))>60){
        faulted_=true;Serial.println("FAULT:TARGET_BOUND");return;
      }
      ids[count]=uint8_t(11+i);acc[count]=1;
      positions[count]=int16_t(target[i]);speeds[count]=20;++count;
    }
    if(!count){faulted_=true;Serial.println("FAULT:EMPTY_LEG");return;}
    before_=check;
    st.SyncWritePosEx(ids,uint8_t(count),positions,speeds,acc); // One bus write, no retry.
    if(st.Error!=0){faulted_=true;Serial.println("FAULT:WRITE_UNCERTAIN");return;}
    sent_=true;finished_=false;verified_=false;sent_ms_=millis();
    Serial.printf("LEG_SENT:%s:%u:%u\n",rocellDiagnosticInstance,next_leg_+1,count);
  }
  Pose snapshot_{},before_{};
  char input_[64]{};size_t size_=0;uint32_t sent_ms_=0;
  unsigned next_leg_=0;bool attempted_[5]{},snapshot_valid_=false,
    sent_=false,finished_=false,verified_=false,faulted_=false;
};
}
