# Initial state
The project started as a very simple script that would do rudimentary task counting using `orgparse` (about 115 lines of Python, no tests). The remainder was implemented by Claude Sonnet 4.5 (with a touch of Opus and Haiku) on the Pro plan via Emacs agent-shell & OpenCode.

Following are the prompts I used for expanding the project.
Whenever clarifying questions were asked I provided answers (not included). Each time a plan was made with the `plan` agent, then I would switch the agent to `build` and ask it to proceed according to the plan. Some manual intervention was needed here and there to contain the slop.

The Quota on the Pro plan was quick to run out due to a myriad of individual tool calls when making edits and repeated, duplicate command runs (e.g `pytest` followed by `pytest --cov`), a set of helpers was introduced manually to try to contain the AI's thirst for spinning in circles.

# Features built with AI

## ✅ Linter & formatter on pre-commit hook
Add a linter, code formatter and type-checker with sane configurations (default, unless the current code does not pass either of the steps). Make sure that the AGENTS.md is updated with the instructions on running these tools. Add a pre-commit hook to the repository Git config that ensures the linter, formatter & type-checker runs each time the code is commited.

Comment: AI did pretty good, it introduced the `Any` type but it was easy to fix.

## ✅ CLI params
Add `argparse` to the CLI module. The value for the `max_results` parameter should be configurable with a default of 100. The values for `TAGS`, `HEADING` and `BODY` should be read from a file if the parameter is provided, or default to their current values if parameters are not provided.
Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

Comment: AI did pretty well, asked some clarifying questions and then proceeded with the implementation correctly.

## ✅*️ Frequency abstraction
Abstract frequencies returned by `analyze()` into a separate class. The class should contain a single field called `total`. `analyze()` should produce dictionaries mapping tags into these frequencies objects instead of the current `dict[str, int]`.
This change should be fairly small and localized to the @src/core.py module.
Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

Comment: This simple change took a long time, probably longer than doing it manually. In the end it works, but it wasted a lot of the quota.

## ✅*️ One entry point
Please combine the @src/main.py and @src/cli.py entry points into just @src/cli.py. No backwards compatibility is necessary, but make sure that all tests keep working. Update the @README.md file to reflect the new usage.

Comment: This trival rename/consolidation took a long time and about 10% of the quota since each instance of the `main.py` invocation in tests was done as a separate tool call. I should really read these tests and ask the AI to clean them up first.

## ✅*️ Stats result
Abstract the values returned by `analyze()` into a separate stats dataclass that represents the whole result: including `total` tasks, `done` tasks, tag frequencies, heading word frequencies and body word frequencies.
Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

Comment: Another trivial change that took a long time for the AI to implement and a sizable chunk of the quota.

## ✅ Extra frequencies
Add extra fields to the `Frequency` class: `simple`, `regular`, `hard`. All of these should be integers defaulting to 0.
The values for these fields computed for each tag should be based on the `gamify_exp` property. When `analyze()` considers a task that has the `gamify_exp` property set, it should check the value of that property:

- when property value is lower than 10 it is a simple task - the `simple` frequency should be incremented,
- when it is between 10 and 20 it is a regular task - the `regular` frequency should be incremented,
- and when it is more than 20 it is a hard tas - the `hard` frequency should be incremented.

By default, if `gamify_exp` is missing, assume a task is a regular task. If `gamify_exp` is of the form `(X Y)` where both `X` and `Y` are numbers, use `X` as the basis for the estimation. In all other cases, when the `gamify_exp` property isn't an integer or a `(X Y)` pair, assume the task is a regular task. For repeated tasks assume the same value for `gamify_exp` for all repetitions. In every case the `total` frequency should also be incremented for each task.

Adjust the `Frequency.__repr__()` function to properly show all frequency values.

Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

Comment: Surprisingly enough, this one went very well and resulted in a working change quickly at about 15% quota usage. An especially curious aspect was that the AI tested how to access `OrgNode` properties by running a Python REPL and checking it out by itself.

## ❌ CLI switch for the top tag criteria
Add a CLI parameter called `--tasks`. The values accepted by that parameter are `simple`, `regular`, `hard` and `total`. The default is `total`. The parameter should be used for the sorting of the results of the analysis - when the user requests `--tasks hard` the results should be ordered by the `hard` frequency and `max_items` of them should be displayed.
The display should only involve the selected frequency -in the example, only the value for `hard` frequency would be shown for each tag. The display should always display just tag name and integer frequency values. For `--tasks total` only the `total` frequency should be displayed.

Make sure to adjust the README with the updated usage.
Make sure to run the test suite and fix the issues that might have been introduced.

Comment: The AI got fixated on the potential breaking changes and needed multiple confirmations that it is indeed OK. It computed a very large plan of action and estimated abotu 85 minutes (!) for its execution. The plan alone took 15% of the quota, but the execution was actually swift, taking about 5 minutes and extra 30% of quota (!) ending prematurely before it got to run the linter & test suite to confirm that the change actually didn't break anything. I did that manually and it was all good.

## ✅ Proper build setup
While the quota ran out I added Poetry as a build system for this project, but currently the code itself doesn't conform to the prefered CLI application layout of a Python project. Please add a `orgstats` as a package-level directory in `src/` and move the code logic to that package. Please adjust the build configuration in @pyproject.toml to build a CLI (there is a commented out stub that you can expand). Please adjust the AGENTS.md file to reflect the new project layout. Please make sure the application works as expected by running all the validation checks via `poetry run task check`, fix any issues that might have been introduced.

Comment: The AI did well making all the changes correctly. It made a lot fewer command calls to validate that each step works, as expected, but still halucinated the need to verify runnig the application three different styles "for backwards compatibility".

## Devcontainers setup
A docker container for running the repo commands in.

## Pair-wise relations
Compute which tags are frequently used together.

## Skill time ranges
Compute time distributions for all tags

## Graphviz/Dot output

## D3 visualization - tag cloud

## D3 visualization - relations graph
Node size is how many tasks are related to a tag. Closeness is how related these are.

## D3 visualization - tag charts over time
Allow selecting specific tags or top tags.
