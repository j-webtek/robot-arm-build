// Offline-only structural validator for a future volatile reviewed-hover owner.
// Not included in the installed firmware and not an actuation route.
#pragma once
#include <cstddef>
#include <cstdint>

namespace rocell_diag {
struct ReviewedHoverManifest {
  static constexpr unsigned max_legs = 16;
  static constexpr uint16_t speed = 20;
  static constexpr uint8_t acceleration = 1;
  enum Pose : uint8_t {
    A_CLEAR = 0, A_HOVER = 1, A_DOWN = 2,
    B_CLEAR = 3, B_HOVER = 4, B_DOWN = 5,
  };
  static constexpr uint16_t goals[6][7] = {
    {2047,2075,2039,2600,2233,2040,2047},
    {2047,2093,2021,2618,2197,2040,2047},
    {2047,2105,2009,2630,2173,2040,2047},
    {1994,2075,2039,2600,2233,2040,2047},
    {1994,2093,2021,2618,2197,2040,2047},
    {1994,2105,2009,2630,2173,2040,2047},
  };
  static bool edge(uint8_t from, uint8_t to) {
    switch(from) {
      case A_CLEAR: return to == A_HOVER || to == B_HOVER;
      case A_HOVER: return to == A_DOWN || to == A_CLEAR;
      case A_DOWN: return to == A_HOVER;
      case B_CLEAR: return to == B_HOVER || to == A_HOVER;
      case B_HOVER: return to == B_DOWN || to == B_CLEAR;
      case B_DOWN: return to == B_HOVER;
      default: return false;
    }
  }
  static bool selected_step(uint8_t from, uint8_t to) {
    if(from >= 6 || to >= 6 || !edge(from,to)) return false;
    bool changed = false;
    for(unsigned joint = 0; joint < 7; ++joint) {
      const int delta = int(goals[to][joint]) - int(goals[from][joint]);
      const int magnitude = delta < 0 ? -delta : delta;
      if(!magnitude) continue;
      changed = true;
      if(magnitude < 10 || magnitude > 60) return false;
    }
    return changed;
  }
  static bool validate(const uint8_t* pose_ids, size_t count) {
    if(!pose_ids || !count || count > max_legs) return false;
    uint8_t prior = A_CLEAR;
    for(size_t leg = 0; leg < count; ++leg) {
      if(!selected_step(prior,pose_ids[leg])) return false;
      prior = pose_ids[leg];
    }
    return true;
  }
};
}
