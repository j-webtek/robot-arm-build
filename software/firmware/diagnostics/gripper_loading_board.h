// Dedicated stylus-loading image. No generic JSON command parser.
// The only actuator commands are bounded manual steps on servo 17 over USB.
#pragma once
#include "characterization_board_services.h"
#include <cstdlib>
#include <cstring>

namespace rocell_diag {
class GripperLoadingBoard {
 public:
  using Pose=ShoulderPreloadPose;
  void begin(){
    server.on("/rocell/gripper-loader/capabilities",HTTP_GET,[this](){
      char out[256];
      snprintf(out,sizeof(out),
        "{\"schema\":\"rocell.gripper_loader.v2\",\"boot_id\":\"%s\","
        "\"one_open_write_max\":true,\"manual_close_steps_max\":4,"
        "\"automatic_close\":false,\"other_joint_writes\":false}",
        rocellDiagnosticInstance);
      server.sendHeader("Cache-Control","no-store");
      server.send(200,"application/json",out);
    });
  }
  void poll(){
    while(Serial.available()){
      const char ch=char(Serial.read());
      if(ch=='\n'){
        input_[size_]=0;
        dispatch(input_);
        size_=0;
      }else if(ch!='\r'){
        if(size_>=sizeof(input_)-1){size_=0;Serial.println("FAULT:LINE_TOO_LONG");}
        else input_[size_++]=ch;
      }
    }
    if(sent_&&!finished_&&uint32_t(millis()-sent_ms_)>=8000){
      finished_=true;
      Pose after{};
      if(!sample(after)){faulted_=true;Serial.println("FAULT:POST_READ");return;}
      for(unsigned i=0;i<6;++i){
        if(std::abs(int(after.position[i])-int(before_.position[i]))>16||
           after.goal[i]!=before_.goal[i]||after.torque[i]!=before_.torque[i]){
          faulted_=true;Serial.println("FAULT:OTHER_JOINT_CHANGED");return;
        }
      }
      if(after.goal[6]!=target_||
         std::abs(int(after.position[6])-int(target_))>25){
        faulted_=true;Serial.println("FAULT:GRIPPER_NOT_AT_TARGET");return;
      }
      verified_=true;
      if(opening_)open_complete_=true;
      Serial.printf(opening_?"OPEN_VERIFIED:%u:%u\n":"CLOSE_VERIFIED:%u:%u\n",
                    unsigned(before_.position[6]),
                    unsigned(after.position[6]));
    }
  }
 private:
  bool sample(Pose& pose){
    auto admitted=[](){return st.End==0&&rocellHoldHealthy(nullptr)&&
                              rocellConfigurationBusInactive(nullptr);};
    return FixedPairReanchorAcquisition::sample(st,rocellConfiguredClock,pose,admitted);
  }
  static bool stable(const Pose& a,const Pose& b){
    for(unsigned i=0;i<7;++i){
      if(std::abs(int(a.position[i])-int(b.position[i]))>8||
         a.goal[i]!=b.goal[i]||a.torque[i]!=b.torque[i])return false;
    }
    return true;
  }
  static bool reviewed_pose(const Pose& pose){
    static const uint16_t positions[7]={2041,2081,2033,2609,2233,2041,2047};
    static const uint16_t goals[7]={2047,2075,2039,2600,2233,2040,2047};
    for(unsigned i=0;i<7;++i){
      if(std::abs(int(pose.position[i])-int(positions[i]))>40||
         pose.goal[i]!=goals[i]||pose.torque[i]!=1)return false;
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
                    unsigned(sent_),unsigned(finished_),unsigned(verified_));
      return;
    }
    char expected[48];
    snprintf(expected,sizeof(expected),"OPEN:%s",rocellDiagnosticInstance);
    if(std::strcmp(line,expected)!=0){
      char close[52];
      snprintf(close,sizeof(close),"CLOSE:%s:%u",rocellDiagnosticInstance,
               unsigned(close_attempts_+1));
      if(std::strcmp(line,close)!=0||!open_complete_||!verified_||faulted_||
         close_attempts_>=4||!snapshot_valid_){
        Serial.println("FAULT:COMMAND_REJECTED");return;
      }
      ++close_attempts_; // Consume this exact step even if its prewrite check fails.
      Pose fresh{},check{};
      if(!sample(fresh)||!stable(snapshot_,fresh)||!sample(check)||
         !stable(fresh,check)||check.position[6]+50>original_count_||
         check.goal[6]!=last_target_){
        faulted_=true;Serial.println("FAULT:CLOSE_PREWRITE_POSE");return;
      }
      before_=check;target_=uint16_t(check.position[6]+50);
      opening_=false;verified_=false;finished_=false;
      const int result=st.WritePosEx(17,target_,30,1); // One write, no retry.
      if(result!=1||st.Error!=0){
        faulted_=true;finished_=true;Serial.println("FAULT:CLOSE_WRITE_UNCERTAIN");return;
      }
      last_target_=target_;sent_ms_=millis();
      Serial.printf("CLOSE_SENT:%s:%u:%u\n",rocellDiagnosticInstance,
                    unsigned(close_attempts_),unsigned(target_));
      return;
    }
    if(attempted_||!snapshot_valid_||faulted_){
      Serial.println("FAULT:ONE_USE_OR_NO_SNAP");return;
    }
    attempted_=true;
    Pose fresh{},check{};
    if(!reviewed_pose(snapshot_)||!sample(fresh)||!stable(snapshot_,fresh)||
       !sample(check)||!stable(fresh,check)||!reviewed_pose(check)||
       check.position[6]<1000){
      faulted_=true;Serial.println("FAULT:PREWRITE_POSE");return;
    }
    before_=check;
    original_count_=check.position[6];
    target_=uint16_t(check.position[6]-200);
    const int result=st.WritePosEx(17,target_,40,1); // One write; never retry.
    if(result!=1||st.Error!=0){faulted_=true;Serial.println("FAULT:WRITE_UNCERTAIN");return;}
    sent_=true;opening_=true;last_target_=target_;sent_ms_=millis();
    Serial.printf("OPEN_SENT:%s:%u\n",rocellDiagnosticInstance,unsigned(target_));
  }
  Pose snapshot_{},before_{};
  char input_[64]{};size_t size_=0;uint16_t target_=0,last_target_=0,
    original_count_=0;uint32_t sent_ms_=0;unsigned close_attempts_=0;
  bool snapshot_valid_=false,attempted_=false,sent_=false,finished_=false,
    verified_=false,opening_=false,open_complete_=false,faulted_=false;
};
}
