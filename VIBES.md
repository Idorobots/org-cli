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

## ❌ Default help message
When no files are provided to the CLI command the usage message should be printed instead of the empty results.

Comment: After planning the change I figured it would take the AI longer than applying the change manually, so I aborted the plan execution.

## ✅ Pair-wise relations
I'd like to expand the analysis done in `analyze()` to inculde computation of pair-wise relations between tags/words.
Introduce a new class called `Relations` with a field called `name` and another named `relations`. The `name` property will hold the tag while the `relations` field should be a dictionary representing the frequencies two tags are used together.
Add fields to the `AnalysisResult` class to store the results of the computation. The fields should be called `tag_relations`, `heading_relations` and `body_relations`, and should be a mapping of tag/word name to the newly created `Relations` objects.

Update the `analyze()` function to compute tag pairs and increment the relation counts in the `Relations` objects. Here's an example:
- When tags contain `tagA`, `tagB` and `tagC` the function should increment the relation frequencies for:
  - `tag_relations[tagA].relations[tagB]`
  - `tag_relations[tagB].relations[tagA]`
  - `tag_relations[tagA].relations[tagC]`
  - `tag_relations[tagC].relations[tagA]`
  - `tag_relations[tagB].relations[tagC]`
  - `tag_relations[tagC].relations[tagB]`

That is, for each pair increment the frequencies between both tags. Make sure the pairs are not duplicated when computing pair-wise relations, we want to take each pair into account once for each of the tags. It is OK that each relation is duplicated for each tag in the relation.
Make sure that there are no relations of a tag to itself.
When repeated tasks are concerned, increment the relations for each repeated task (as if each repetition was an instance of the task).
The results for tags, heading and body should be computed separately and returned with the `AnalysisResult`. The `gamify_exp` is not to be taken into account.
The CLI output should not be affected yet.

Comment: The AI implemented the functionality pretty well, it did miss some refactoring opportunities and disabled Linter rules complaining about code complexity.

## ✅ Refactor analyze()
The `analyze()` function is fairly large and there are some opportunities for refactoring. Please move the normalized tag lists above the for loops computing the frequencties and abstract the frequency computation into a separate function called `compute_frequencies()`. The function should take the set of items to consider, a dictionary mapping items into their frequencies and a count of repetitions. Difficulty should also be passed to the function. Please remove the linter exclusion from `analyze()` and ensure that it conforms to the linter rules.
Please refactor the relevant tests to test the new function separately.

Comment: The AI has done a good job, doing exactly what I asked for without any extra bits.

## ✅ Skill time ranges
I'd like to compute the time ranges for all tags/words.
For that functionality, please add a new class called `TimeRange` with two fields `earliest`, `latest`. Both of these fields will be dates the tag was first and last encountered.
The values for these field will come from the tasks stated completion times. That is, for repeated tasks, take the earliest task that is in `DONE` state (`repeated_task.after == "DONE"`).
As a fallback, if a task does not have any repeats, assume the closed timestamp as the time of occurance (`task.closed`).
If closed timestamp is not available, assume the scheduled time as the time of occurance (`task.scheduled`). If that is missing too, assume the deadline time as the time of occurance (`task.deadline`). Otherwise ignore the task.
For each such occurance, the tags time range should be updated so that the `earliest` timestamp represent the earliest date encountered in the data, while the `latest` timestamp represents the latest date encountered in the data.
Do not modify the CLI output just yet.

Comment: The AI explored the structure of `orgparse.OrgNode` and repeated tasks ignoring the details presented on the prompt. It did a good job nontheless.

## ✅ Skill timeline
Expand the `TimeRange` class with another field called `timeline`. This timeline will be used to chart a tag's occurrence over time.
The `timeline` will be a list of all occurances of the task - the dates without the time component paired with an integer representing the count of occurances on that day. You can use a dictionary `dict[date, int]` to represent that. It makes sense to update the `TimeRange.update()` function to also maintain the occurrence list.
Make sure that the timeline's granularity is a day, so two tasks occurring on the same day at different times should both increment the same position on the timeline.
Make sure that repeated tasks are taken into account - each repeat should be reflected on the timeline.
Do not modify the CLI output just yet.

Comment: The AI implemented the change, while I was cleaning some slop resulting in broken test cases. The AI decided it wasn't responsible for these, so it left them as is. When asked to address the failures afterwards, it reinstituted the slop.

## ✅ Times in command output
Display the earliest, latest & most "intense" day for the top `max_results` entries for tags, heading and body.
To achieve that, update the `TimeRange.__repr__` function to find the most "intense" day (highest number of entries related to that tag on that day) and show it as part of the representation `top_day=<date>`. When there are multiple days with equal number of occurrences, select the first one. If there are no occurrences in the timeline, show `None` as the top day.
The time range results should follow the "Top tags" etc sections in the output and be limited to just the `max_results` entries, same as the top tags sections.
This will cause a lot of output to be generated, so modify the default `max_results` parameter value to 10 instead of 100.
Please add some rudimentary tests for this new CLI output, but don't bother with very complex test cases.

Comment: The AI took the "don't bother" part very seriously and didn't write any tests for the CLI output of the time ranges. It did add some tests for the representation of `TimeRange` though.

## ✅ CLI switch to select tags, heading and body
Add a CLI parameter called `--show` that takes either `tags`, `heading` or `body` with a default of `tags`.
This switch will control what the CLI is displaying - either top tags & time range or heading or body.
The application should compute all the values regardless of the switch (we will address that later).
In either case, both the top frequencies and time ranges should be shown.

The output should be adjusted to list each tag on a separate line with frequency, earliest and latest dates and the top day plus the count on that day.
Please don't adjust the `__repr__` functions and instead compute these values as part of the `cli.py` module for display purposes only.

Comment: The AI did good. No comments here.

## Relations in command output
Add a new CLI parameter called `--max_relations` that takes an integer and defaults to 3.
Display the top `max_relations` relations for each of the top results in the output.
Each relation can be a separate line following each tag line, but make sure to indent these so they are visually distinct.
For each relation display the name of the other tag in the relation and the frequency of occurrances of that relation.
Here's an example output:

```
devops: count=2481, earliest=2011-11-18, latest=2026-02-05, top_day=2023-03-26 (11)
    linux (147)
    aws (42)
    azure (21)
algorithms: count=1208, earliest=2013-01-07, latest=2024-12-11, top_day=2014-08-16 (25)
...
```

Add some rudimentary tests for this functionality (not very complex, just sanity check if the output looks a-ok).

## Compute relations separately for different difficulties

## Compute separate time ranges separately for different difficulties

## Only compute the stuff that's needed
Split analyze to produce results only for tags/heading/body and select that with the CLI switch.

## hasattr() slop
Remove it and use OrgNode instead of Mocks.

## Devcontainers setup
A docker container for running the repo commands in.

## Graphviz/Dot output

## D3 visualization - tag cloud

## D3 visualization - relations graph
Node size is how many tasks are related to a tag. Closeness is how related these are.

## D3 visualization - tag charts over time
Allow selecting specific tags or top tags.

