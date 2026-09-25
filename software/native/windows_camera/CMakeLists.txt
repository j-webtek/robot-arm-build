cmake_minimum_required(VERSION 3.25)
project(rocell_windows_camera VERSION 0.1.0 LANGUAGES CXX)
if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "This provider requires the reviewed MSVC/Windows SDK build")
endif()
add_executable(rocell_windows_camera camera_worker.cpp)
add_library(rocell_camera_admission STATIC admission_protocol.cpp)
target_compile_features(rocell_camera_admission PUBLIC cxx_std_17)
target_compile_definitions(rocell_camera_admission PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
target_compile_options(rocell_camera_admission PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
target_link_libraries(rocell_camera_admission PUBLIC bcrypt)
target_sources(rocell_windows_camera PRIVATE admission_entry.cpp)
target_link_libraries(rocell_windows_camera PRIVATE rocell_camera_admission)
target_compile_features(rocell_windows_camera PRIVATE cxx_std_17)
target_compile_definitions(rocell_windows_camera PRIVATE UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
target_compile_options(rocell_windows_camera PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
target_link_options(rocell_windows_camera PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_windows_camera PRIVATE mfplat mf mfreadwrite mfuuid ole32 strmiids)
enable_testing()
add_executable(rocell_camera_admission_tests admission_protocol_tests.cpp)
target_compile_options(rocell_camera_admission_tests PRIVATE /W4 /WX /permissive- /utf-8)
target_link_libraries(rocell_camera_admission_tests PRIVATE rocell_camera_admission)
# This separate target has no camera_worker/admission_entry/COM/MF code.
add_test(NAME camera_admission_parser_incapable COMMAND rocell_camera_admission_tests)
set_tests_properties(camera_admission_parser_incapable PROPERTIES TIMEOUT 10)
# Integration child for the parent's owned-pipe test ONLY. It cannot perform a
# camera operation and deliberately does not manufacture a native camera receipt.
add_executable(rocell_camera_admission_entry_tests admission_entry_tests.cpp admission_entry.cpp)
target_compile_definitions(rocell_camera_admission_entry_tests PRIVATE UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
target_compile_options(rocell_camera_admission_entry_tests PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
target_link_options(rocell_camera_admission_entry_tests PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_camera_admission_entry_tests PRIVATE rocell_camera_admission)
# This path exercises pure parsing, bounds and JSON only. It never starts COM/MF.
add_test(NAME camera_contract_self_test COMMAND rocell_windows_camera --self-test)
set_tests_properties(camera_contract_self_test PROPERTIES TIMEOUT 10)

# Metadata extension uses its own strict receipt schema and explicit action;
# it never changes the existing v1 camera-capture receipt or activates a source.
add_library(rocell_identity_metadata STATIC identity_metadata.cpp)
target_compile_features(rocell_identity_metadata PUBLIC cxx_std_17)
target_compile_definitions(rocell_identity_metadata PRIVATE UNICODE _UNICODE NOMINMAX WIN32_LEAN_AND_MEAN)
target_compile_options(rocell_identity_metadata PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
target_link_libraries(rocell_identity_metadata PUBLIC setupapi cfgmgr32)
target_link_libraries(rocell_windows_camera PRIVATE rocell_identity_metadata)
add_executable(rocell_identity_metadata_tests identity_metadata_tests.cpp)
target_compile_definitions(rocell_identity_metadata_tests PRIVATE NOMINMAX)
target_compile_options(rocell_identity_metadata_tests PRIVATE /W4 /WX /permissive- /utf-8 /guard:cf)
target_link_options(rocell_identity_metadata_tests PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)
target_link_libraries(rocell_identity_metadata_tests PRIVATE rocell_identity_metadata)
add_test(NAME identity_metadata_fake_api COMMAND rocell_identity_metadata_tests)
set_tests_properties(identity_metadata_fake_api PROPERTIES TIMEOUT 10)

# Optional cross-language contract check uses the repository's existing Python
# environment and ONLY the incapable FakeApi executable, never real metadata.
get_filename_component(ROCELL_TEST_PYTHON "${CMAKE_CURRENT_SOURCE_DIR}/../../../.venv/Scripts/python.exe" ABSOLUTE)
if(EXISTS "${ROCELL_TEST_PYTHON}")
  add_test(NAME identity_metadata_wire_contract
    COMMAND "${ROCELL_TEST_PYTHON}" "${CMAKE_CURRENT_SOURCE_DIR}/identity_metadata_wire_test.py"
      "$<TARGET_FILE:rocell_identity_metadata_tests>")
  set_tests_properties(identity_metadata_wire_contract PROPERTIES TIMEOUT 15)
else()
  message(STATUS "Existing repository Python environment absent; identity wire CTest not registered")
endif()
