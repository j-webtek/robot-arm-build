// Candidate continuation source comparison; not deployed by the r77 image.
#pragma once
#include <cstdlib>
namespace rocell_diag {
inline bool air_typing_r78_source_joint_verified(int previous_position,
    int expected_goal,int current_position,int current_goal){
  return current_goal==expected_goal&&
         std::abs(current_position-previous_position)<=3&&
         std::abs(current_position-expected_goal)<=12;
}
}
