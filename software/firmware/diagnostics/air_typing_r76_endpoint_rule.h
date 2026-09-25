// Proposed continuation rule. Historical r75 policy/image remains unchanged.
#pragma once
#include <cstdlib>
namespace rocell_diag {
inline bool air_typing_r76_endpoint_joint_verified(int initial_goal,
    int initial_position,int target_goal,int final_position){
  const int command=target_goal-initial_goal;
  const int travel=final_position-initial_position;
  if(!command||std::abs(command)>80||std::abs(travel)>92)return false;
  const int direction=command>0?1:-1;
  if(travel*direction<-1||std::abs(final_position-target_goal)>12)return false;
  if(std::abs(command)<4||travel*direction>=2)return true;
  return std::abs(initial_position-target_goal)<=3&&
         std::abs(final_position-target_goal)<=3;
}
}
