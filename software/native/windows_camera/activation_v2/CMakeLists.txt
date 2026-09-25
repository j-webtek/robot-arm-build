cmake_minimum_required(VERSION 3.25)
project(rocell_windows_camera_activation VERSION 2.0.0 LANGUAGES CXX)
if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "This provider requires MSVC and Windows SDK")
endif()
set(ROCELL_ACTIVATION_PURPOSE "" CACHE STRING "Exactly probe or capture")
if(NOT ROCELL_ACTIVATION_PURPOSE STREQUAL "probe" AND NOT ROCELL_ACTIVATION_PURPOSE STREQUAL "capture")
  message(FATAL_ERROR "Set ROCELL_ACTIVATION_PURPOSE to probe or capture explicitly")
endif()
set(NATIVE "${CMAKE_CURRENT_SOURCE_DIR}/..")
function(reviewed_compile target)
  target_compile_features(${target} PUBLIC cxx_std_17)
  target_compile_definitions(${target} PRIVATE UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
  target_compile_options(${target} PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
  target_include_directories(${target} PUBLIC "${NATIVE}" "${CMAKE_CURRENT_SOURCE_DIR}")
endfunction()
function(reviewed_executable target)
  reviewed_compile(${target})
  target_link_options(${target} PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
endfunction()

add_library(rocell_activation_codec STATIC camera_activation_protocol.cpp
  "${NATIVE}/admission_protocol.cpp" "${NATIVE}/capture_admission_protocol.cpp")
reviewed_compile(rocell_activation_codec)
target_link_libraries(rocell_activation_codec PUBLIC bcrypt)

# Only this target links a real metadata resolver and COM/MF acquisition code.
# It is compiled, never executed by CTest or the build-record workflow.
add_executable(rocell_windows_camera camera_worker.cpp camera_activation_entry.cpp
  camera_activation_result.cpp "${NATIVE}/identity_metadata.cpp")
reviewed_executable(rocell_windows_camera)
if(ROCELL_ACTIVATION_PURPOSE STREQUAL "capture")
  target_compile_definitions(rocell_windows_camera PRIVATE ROCELL_ACTIVATION_CAPTURE_ONLY ROCELL_ENABLE_OWNED_CAPTURE)
else()
  target_compile_definitions(rocell_windows_camera PRIVATE ROCELL_ACTIVATION_PROBE_ONLY)
endif()
target_link_libraries(rocell_windows_camera PRIVATE rocell_activation_codec
  setupapi cfgmgr32 mfplat mf mfreadwrite mfuuid ole32 strmiids)

enable_testing()
foreach(component identity gate launch protocol)
  add_executable(rocell_activation_${component}_tests camera_activation_${component}_tests.cpp)
  reviewed_executable(rocell_activation_${component}_tests)
  if(component STREQUAL "protocol")
    target_link_libraries(rocell_activation_${component}_tests PRIVATE rocell_activation_codec)
  endif()
  add_test(NAME activation_${component}_incapable COMMAND rocell_activation_${component}_tests)
  set_tests_properties(activation_${component}_incapable PROPERTIES TIMEOUT 10)
endforeach()
add_executable(rocell_activation_cleanup_tests "${NATIVE}/camera_cleanup_tests.cpp")
reviewed_executable(rocell_activation_cleanup_tests)
add_test(NAME activation_cleanup_incapable COMMAND rocell_activation_cleanup_tests)
set_tests_properties(activation_cleanup_incapable PROPERTIES TIMEOUT 10)

# Pipe/result interop helper: fixture metadata and exact extracted serialization
# only. No metadata resolver, Windows device adapter, COM/MF, frame writer or
# camera worker. Python tests drive REQUEST/READY/RELEASE against this target.
add_executable(rocell_activation_result_tests camera_activation_result_tests.cpp
  camera_activation_entry.cpp camera_activation_result.cpp identity_serialization_incapable.cpp)
reviewed_executable(rocell_activation_result_tests)
target_link_libraries(rocell_activation_result_tests PRIVATE rocell_activation_codec)
