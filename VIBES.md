# Good Vibes
The goal of the project was to attempt to achieve the fabled 10x productivity boost by vibe-coding as much of the project, while only focusing attention on the parts that matter. Simply put, go as fast as possible, break things and run out of quota. That last part was certainly achieved.

# Initial state
The project started as a very simple script that would do rudimentary task counting using `orgparse` (about 115 lines of Python, no tests). The remainder was implemented by Claude Sonnet 4.5 (with a touch of Opus and Haiku) on the Pro plan via Emacs agent-shell & OpenCode. It was sloperated along the way to a small extent.

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

## ✅*️ Relations in command output
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

Comment: The AI did a good job, but was flabbergasted by the format chosen for the relation display. It did notice, that we're not filtering the relations the same way as we do for frequency computation and proposed it should do that. It also had the linter complain about too many parameters to a function, so it "refactored" it by wrapping some of the params into a tuple.

## ✅*️ Relations filtering
Tag names in relations should be filtered the same way as for freequencies computations, make sure that the exclude lists are applied to the relations "cleaning" the list before displaying the values.
The `max_relations` limit should be applied after the list of relations is filtered.

Comment: AI is back to its old ways of running tests manually despite an explicit instruction not to do that. It is also experiencing LSP errors which it "learned" to ignore, probably taking precious quota.

## ✅*️ Configurable normalization mapping
Currently the `MAP` used by `normalize` to normalize the word names is hard-coded. Please make that value configurable and overridable via a CLI parameter called `--mapping`.
The mapping parameter should take a JSON file mapping words to other words (effectively a `dict[str, str]`). The default value should be the current `MAP` value. That value should then be passed to `analyze()` and used for the normalization logic without affecting the computation logic.

Please make sure to test this functionality and the new CLI parameter.

Comment: AI got a bit fixated at error handling etc, but did the job alright. It did introduce default params not to have to modify all the test cases. I sloperated that myself not changing the net slop amount it seems.

## ✅ Refactor hardcoded lists
Move the `MAP` value and the `TAGS`, `HEADING` and `BODY` exclusion lists to the cli.py module as they are no longer tightly-coupled to the core module.

Comment. This was easy enough, no comments here.

## ✅ Only consider the relevant tasks
The `analyze()` function currently makes a distinction on the task type based on the value of the `gamify_exp` field which it then uses to compute frequencies for all types. I'd like to move that distinction logic outside of the `analyze()` function, so that it accepts a pre-filtered list of nodes which are then analyzed.

To achieve that we first need to remove the `simple`, `regular` and `hard` fileds from the `Frequency` class and only leave the `total` field. The `compute_frequencies()` function needs to only update the `total` count.

The `gamify_exp` parsing should be extracted into a separate helper function called `gamify_exp()`. It should take an `orgparse.OrgNode` and return the integer representing the value of the `gamify_exp` property, or `None` if none is present on a node. Make sure to add this functionality.

The CLI parameter `--tasks` will now determine the function used for filtering the task list. Here is the logic behind this parameter:
- When it is set to `total`, the filter function should leave all the nodes in.
- When it is set to `simple`, the function should leave only the nodes that have a `gamify_exp()` of 10 or lower (currently considered to be "simple" tasks).
- When it is set to `regular`, the function should leave only the nodes that have a `gamify_exp()` of between 11 and 20 (currently considered to be "regular" tasks).
- When it is set to `hard`, the function should leave only the nodes that have a `gamify_exp()` of 21 or above (currently considered to be "hard" tasks).
The parameter will take on more values in the future, but don't worry about that just yet.

The node list passed to `analyze()` must be filtered before being passed into the function according to the value of the `--tasks` parameter. That can be done as part of the `main()` function. Please simplify the test cases for the `analyze()` function with the assumption that the node filtering will be performed beforehand.
Make sure to test the functionality of the node list filtering.

Comment: This one was a long one, but the AI aced it. At least as far as I can tell.

## ❌ Rename --tasks
Rename the `--tasks` CLI parameter to `--filter` and the values that in can take to `simple`, `regular`, `hard` and `all`. The values should determine the behaviour the same as before, only the name of the `total` value is changed to `all`. The default value for this parameter should now be `all`.

Comment: Somehow the AI made this into a very long and time consuming task. Exhausting the remaining 20% of quota. It was possible to continue with the plan the next day by asking the AI to carry on after the interruption.

## ❌ Update the README
Update the README file to account for the recent development.

Comment: Another one that was easier to do manually than let the AI fixate on putting code coverage in the description.

## ✅*️ Only consider the relevant data
Only compute the statistics in tags or heading or body, depending on the value of the `--show` CLI parameter.
To achieve that, simplify the `AnalysisResult` class to only have the following fields:
- `total_tasks`
- `done_tasks`
- `tag_frequencies`
- `tag_relations`
- `tag_time_ranges`
The definitions of these fields should remain unchanged. The logic to compute those fields should remain unchanged.
The `analyze()` function should be updated to take a flag that determines which datum of a task should be considered, either the `tags`, the `heading` or the `body`. The computation performed by `analyze()` should only be peformed on the selected datum and only the values computed for that datum should be returned as part of the `AnalysisResult`.
Regardless of what datum is used, the results for frequencies should end up in the `tag_frequencies` field, et cetera.
Don't worry about backwards compatibility.

Comment: The AI fixated on backwards compatibility and performance gains/penalty (it considered the fact that now one third of the computation is done, but also that the user needs to compute stuff three times). In needed a lot of convincing that this is, in fact, OK.

## ✅*️ Combine exclusion lists
Combine the CLI parameters called `--exclude-*` into one parameter that accepts a single list of words. That list should be used for the tags & relations filtering. The default value should be a list containing the values from `TAGS` combined with the values from `HEADING` and `BODY` (in the case of `BODY` use the values up to and including the `""` value).
Adjust the tests accordingly.

Comment: AI, again, fixated on backwards compatibility despite AGENTS.md explicitly stating it's not required. It did refactor the code fine though, but didn't remove the old, no longer used constants because that would break a lot of tests. This seems to be a common pattern - it values its time like a real boy would.

## ✅*️ Default args slop
Please remove the default argument values from the `analyze()` function and adjust the tests to pass the value manually.
Using default argument vaulues is forbidden in this project.

Comment: It computed a sound plan of operation, but then ran out of quota to actually execute it. It was possible to resume the execution of the plan after the quota reset.

## ✅*️ Hasattr slop
Please remove the usage of `hasattr(node, atrt)` from the function `extract_timestamp()` and adjust the tests to work correctly without using `hasattr()`.
Using `hasattr()` in the logic to make writing tests easier is bad style and you should feel bad about it.

Comment: This went well, it did remove all the occurances of `hasattr` and fixed the tests pretty accurately. It did create extra slop by introducing `MockedEmptyTimestamp` in each file that uses mocks, which isn't ideal.

## ✅*️ Mock slop
Please remove the node mocks from the test code. Use `orgparse.node.OrgNode` and `orgparse.date.OrgDateRepeatedTask` instead of the mocks. If it makes sense for a specific test, you can create fixtures for most of the tests and load those fixtures to test againts real-life node values..
The goal is not to use any mocking in the tests.

Comment: The AI did a bunch of investigating, figuring out how to use `orgparse` nodes and then formulated a rather lengthy plan. It took a while to implement, but was otherwise uneventful. It took 40% of the quota (!).

## ✅ SCC
Given the relations between tags, compute the strongly connected components of the graph.
A strongly connected component is a subgraph in which all the nodes are reachable from all the other nodes. In this case, this will be all the tags that are related. Each strongly connected component will form a group of tags. Each group is a separate component - that is, between two distinct groups there are no relations.

Add a new class called `Group` to the core module. The class will represent the grouped tags. It should have a single field for now called `tags: list[str]`. We will eventually expand that in the future.

Create a new function called `compute_groups()` that will do tag grouping based on strongly connected components algorithm. For the computation only consider `max_relations` count of relations for each tag. That is, pass the value of `max_relations` to the function and limit the graph to just the `max_relations` top relations when grouping the tags. Make sure to add tests that test the implementation of this function.

Extend the `AnalysisResults` class to include a new field called `tag_groups: list[Group]`. This will hold the strongly connected components grouping.

Extend the `analyze()` function to compute the strongly connected components and save the values in the `tag_groups` field. Pass the `max_relations` configuration parameter to the function, so that it can be used by `compute_groups()`. Do not use default argument values for this parameter. Make sure to update the tests to pass the value along.

The grouping computation will be performed on the filtered node list and limited to just the `max_relations` of relations.

Expand the display to include a section on groups right after the top tags. For each group in the results list the tags in that group like this:

```
Tag groups:
  projectmanagement, jira

  debugging, erlang, electronics, xmpp

  ...
```

Comment: The AI computed a sound plan, but then ran out of quota before it could finish implementing it. The bulk of the quota was spent on the tool calls for all the single-line edits. After the quota reset, it finished the implementation properly.

## ✅ Additional relation filter
The SCC works great, but the output produced is kinda wonky - it still produces quite a few groups.
Please add an additional CLI parameter called `--min-group-size` that takes an integer and defaults to 3.
This parameter should be used to filter out groups smaller than the threshold during display.

Comment: The AI proposed to rename origial `--group-threshold` parameter to something better, like `--min-group-size`. Can't argue with that. This was easier to do manually though.

## ❌ Typed tests
I enabled type checking the tests files. Please add type signatures to the test functions and ensure that the type checking passes fine for all the test files.
You can run the checks by calling `poetry run task check`.

Comment: This one I expected to be a lengthy one - there were 428 type errors to begin with. Fortunately, I ran out of the weekly quote before the AI got to waste all the quota. After the weekly quota reset, I executed another plan and proceeded to implementation. It took a long time and 30% of the quota, but it added types with regexes :grimacing:. It also added a lot of slop by typing stuff as `Any` that had to be manually fixed.

## ❌ Devcontainers setup
A docker container for running the agentin.

Comment: Since the quote ran out, I implemented this myself.

## ✅*️ General stats - todo histogram
I'd like to add more stats to the analysis.

Please add a new class called `Histogram` that will hold a distribution of tasks in a field called `values: dict[str, int]`. This class will be used to store properties like "how many tasks of a given TODO state there are in the archive" and also other distributions like "how many tasks were done on each day of the week".

For the todo state histogram:
- extend `AnalysisResults` with a new field called `task_states: Histogram`,
- take into account the following states: `TODO`, `DONE`, `DELEGATED`, `CANCELLED`, `SUSPENDED` and `other` if a node does not have a todo state,
- increment the histogram `values` for a given state for each occurance of the task - that includes repeated tasks too,
- use the `repeated_task.after` property for the state of repeats,
- use the `node.todo` property for the state of the nodes itself.

Don't worry about the other use cases just yet, we'll add them one at a time.
Please remove the `done_tasks` field from the `AnalysisResult` class and use the histogram-computed value instead for the CLI output.

Display the values for different todo states in the CLI output. You can create a new section for this and replace the `done tasks` one with it.

Comment: The AI did a nice job. It, correctly, noticed that `orgparse` only handles `DONE` and `TODO` states and worked around it (in tests). The code appeared to work correctly despite the fact that nothing was done to make `orgparse` recognize different states. When confronted about how this was acomplished, the AI noted that it wasn't and figured out that the code working was purely incidental (the logbook repeat state being preferred to the actual todo state of the node).

## ✅*️ Configurable todo, completed and cancelled states.
Please add two CLI switches called `--todo-keys` and `--done-keys` with the following semantics:
- `--todo-keys` names a comma separated list of not completed states a task can be in,
- `--done-keys` nams a comma separated list of completed states a taks can be in.
The default values for these parameters should be:
- for `--todo-keys` - `TODO`,
- for `--done-keys` - `DONE`.

The values of these keys should be "configured" in the content passed to `orgparse.loads()` as the accepted TODO states.
The format of that configuration is:

```
#+TODO: {TODO_KEYS} | {DONE_KEYS}
```

It should be prepended to the content.

Please update the `analyze()` function not to make an assumption on the set of tags that can be encountered, i.e. omit checking if the actual node state a taks is in is defined in the histogram object. We want to compute the full distribution without making any assumptions on the data. We can't expect the configured `--todo-keys` and `--done-keys` to be the exhaustive list, but it's worth defining these nonetheless.

Please update the semantics of the `other` histogram value to be `none` instead - only the tasks that don't have a state will end up there.

Please update the CLI output to show all detected states, including the `none` state.

Comment: They AI was extatic about the backwards compatibility breaking possibilities and needed convincing that it's fine. It then implemented the feature pretty well, revealing exactly how broken the previous implementation was. It also made the task state counts inconsistent - counting states twice if a task wask repeated. I asked the AI to fix that issue within the same session, just to find out that the quota run out again.

## General stats - day histogram
I'd like to add another histogram to the analysis - this time a distribution of tasks completed on different days of the week.

For the day of week histogram:
- extend `AnalysisResult` with a new field called `task_days: Histogram`,
- take into account only the tasks in the following states: `DONE`,
- increment the histogram `values` for each occurance of the task - that includes repeated tasks too,
- use the timestamp of a task to extract the date and use `datetime.weekday()` to extract the day of week - you might need to map that value to a string representation: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`,
- the timestamp should be computed the same way as was done in `extract_timestamp()`,

Display the values for week days in the CLI output. You can add that after the todo state breakdown.

## General stats - time range
I'd like to compute a global time range of all tasks completed that are in the archive.

Extend the `AnalysisResult` class with a new field called `timerange: TimeRange` which will hold the time line for all the completed tasks.

Extend the `analyze()` function to compute the over-all timerange of the tasks:
- timestamp of the earliest task,
- timestamp of the latest task,
- the general timeline - inclusive of all tasks that were completed (in the `DONE` state), including their repeats,

Only consider tasks that are in the `DONE` state. This should be analogous to the per-tag timeranges computed before, but should apply regradless of the datum used to all tasks.

Extend the CLI output to include the earliest & latest timestamps somewhere near the total tasks count.

## General stats - other
I'd like to add a few more stats to the analysis results:

- total number of tasks in the system (inclusive of their repeats - this is already computed),
- average tasks done per day (computed as the total number of tasks completed divided by the number of days between the earliest and latest task occurances globally),

Please display these values on the CLI output.

## More task filters
- gamify_exp above
- gamify_exp under
- Add CLI parameters for from & until, with defaults and filter the tasks to only consider the tasks within the given time range.

## ASCII plots
Use an ascii plotting library to plot tag activity over time. Each plot should be a bar chart with at most 50 buckets. Each bucket will represent 1/50 of the total time range within which te tag was active. If the tag was active for more than 50 days, group the activity into buckets, sum the occurances and plot the sums. If the tag was active for fewer than 50 days, plot only as many buckets as makes sense. Make sure to take into account all days, even those with no tag activity on that day. These should have a value of 0. You can first expand the timeline with the missing days of no activity, then determine the buckets and compute sums of activity per bucket and then plot the results.
There should be an indication of the start and end dates besides the plot.

- pie-chart of the states
- pie chart of the week days
- Adjust the tag plots to also reflect the same "global"" time range.

## Better heading & body parsing

## Output abstraction
We will be adding more output options, for instance JSON output, visualization output, etc.

## Graphviz/Dot output

## D3 visualization - tag cloud

## D3 visualization - relations graph
Node size is how many tasks are related to a tag. Closeness is how related these are.

## D3 visualization - tag charts over time
Allow selecting specific tags or top tags.

