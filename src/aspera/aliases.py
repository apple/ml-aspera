#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
# the name of a module under src/aspera/apps
AppName = str
# the name of a human written example module, found in
# repo root under examples/
ExamplesModule = str
# a string representation a python function representing
# which can be executed in a REPL environment
ProgramStr = str
# a string representation for the imports that should
# be executed before a program
ImportStr = str
# a comment made by the data curator while checking the
# program correctness
AnnotatorComment = str
# a module under src/aspera/runtime_state_generation_tools where docs for
# tools the agent can use for setting up the environment
# are documents
SimulationModuleName = str
# the name of a function implemented in src/aspera/runtime_state_generation_tools_implementation/*
# and documented in src/aspera/runtime_state_generation_tools
SimulationToolName = str
# SimulationModuleName::SimulationToolName
SimulationTool = str
# a module under src/aspera/execution_evaluation_tools where docs for
# tools the agent can use for writing evaluation functions
EvaluationModuleName = str
# the name of a function implemented in src/aspera/testing_tool_implementations/*
# and documented in src/aspera/execution_evaluation_tools
EvalToolName = str
# EvaluationModuleName::EvalToolName
EvaluationTool = str
# generic for SimulationModuleName |EvaluationModuleName
ModuleName = str
# as above for tool names
FunctionName = str
# the text of a query
Query = str
# an integer identifying the query
QueryIdx = str
ShardPath = str
