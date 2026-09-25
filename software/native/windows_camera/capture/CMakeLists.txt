cmake_minimum_required(VERSION 3.25)
project(rocell_windows_camera_capture VERSION 0.1.0 LANGUAGES CXX)
if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "This development provider requires MSVC and Windows SDK")
endif()
set(NATIVE "${CMAKE_CURRENT_SOURCE_DIR}/..")
function(reviewed_compile target)
  target_compile_features(${target} PUBLIC cxx_std_17)
  target_compile_definitions(${target} PRIVATE UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
  target_compile_options(${target} PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
  target_include_directories(${target} PUBLIC "${NATIVE}")
endfunction()
add_library(rocell_capture_admission STATIC "${NATIVE}/admission_protocol.cpp" "${NATIVE}/capture_admission_protocol.cpp")
reviewed_compile(rocell_capture_admission)
target_link_libraries(rocell_capture_admission PUBLIC bcrypt)
add_library(rocell_capture_identity STATIC "${NATIVE}/identity_metadata.cpp")
reviewed_compile(rocell_capture_identity)
target_link_libraries(rocell_capture_identity PUBLIC setupapi cfgmgr32)

# Compiled only; never registered as a release and never executed by CTest.
add_executable(rocell_windows_camera "${NATIVE}/camera_worker.cpp" "${NATIVE}/admission_entry.cpp" "${NATIVE}/capture_admission_entry.cpp")
reviewed_compile(rocell_windows_camera)
target_compile_definitions(rocell_windows_camera PRIVATE ROCELL_ENABLE_OWNED_CAPTURE)
target_link_options(rocell_windows_camera PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_windows_camera PRIVATE rocell_capture_admission rocell_capture_identity mfplat mf mfreadwrite mfuuid ole32 strmiids)

# Recompile the unchanged probe branch with capture disabled in this new build
# directory. This proves old CMake inputs still compile without touching old bins.
add_executable(rocell_windows_camera_probe_compile_check "${NATIVE}/camera_worker.cpp" "${NATIVE}/admission_entry.cpp")
reviewed_compile(rocell_windows_camera_probe_compile_check)
target_link_options(rocell_windows_camera_probe_compile_check PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_windows_camera_probe_compile_check PRIVATE rocell_capture_admission rocell_capture_identity mfplat mf mfreadwrite mfuuid ole32 strmiids)

enable_testing()
# Shared production cleanup ordering, with no Windows/device adapter linked.
add_executable(rocell_camera_cleanup_tests "${NATIVE}/camera_cleanup_tests.cpp")
reviewed_compile(rocell_camera_cleanup_tests)
target_link_options(rocell_camera_cleanup_tests PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
add_test(NAME camera_cleanup_incapable COMMAND rocell_camera_cleanup_tests)
set_tests_properties(camera_cleanup_incapable PROPERTIES TIMEOUT 10)
add_executable(rocell_camera_capture_admission_tests "${NATIVE}/capture_admission_protocol_tests.cpp")
reviewed_compile(rocell_camera_capture_admission_tests)
target_link_options(rocell_camera_capture_admission_tests PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_camera_capture_admission_tests PRIVATE rocell_capture_admission)
add_test(NAME camera_capture_parser_incapable COMMAND rocell_camera_capture_admission_tests)
set_tests_properties(camera_capture_parser_incapable PROPERTIES TIMEOUT 10)

# This inherited-pipe target has no camera_worker, identity, COM, MF or device
# libraries; its completion is expressly not a camera capture receipt.
add_executable(rocell_camera_capture_admission_entry_tests "${NATIVE}/capture_admission_entry_tests.cpp" "${NATIVE}/capture_admission_entry.cpp")
reviewed_compile(rocell_camera_capture_admission_entry_tests)
target_link_options(rocell_camera_capture_admission_entry_tests PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_camera_capture_admission_entry_tests PRIVATE rocell_capture_admission)

get_filename_component(TEST_PYTHON "${NATIVE}/../../../.venv/Scripts/python.exe" ABSOLUTE)
if(EXISTS "${TEST_PYTHON}")
  add_test(NAME camera_capture_pipe_incapable
    COMMAND "${TEST_PYTHON}" "${CMAKE_CURRENT_SOURCE_DIR}/admission_entry_wire_test.py"
      "$<TARGET_FILE:rocell_camera_capture_admission_entry_tests>")
  set_tests_properties(camera_capture_pipe_incapable PROPERTIES TIMEOUT 40)
endif()
