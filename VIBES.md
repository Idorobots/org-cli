# Good Vibes
The goal of the project was to attempt to achieve the fabled 10x productivity boost by vibe-coding as much of the project, while only focusing attention on the parts that matter. Simply put, go as fast as possible, break things and run out of quota. That last part was certainly achieved.

# Initial state
The project started as a very simple script that would do rudimentary task counting using `orgparse` (about 115 lines of Python, no tests). The remainder was implemented by Claude Sonnet 4.5 (with a touch of Opus and Haiku) on the Pro plan via Emacs agent-shell & OpenCode. It was sloperated along the way to a small extent.

Following are the prompts I used for expanding the project.
Whenever clarifying questions were asked I provided answers (not included). Each time a plan was made with the `plan` agent, then I would switch the agent to `build` and ask it to proceed according to the plan. Some manual intervention was needed here and there to contain the slop.

The Quota on the Pro plan was quick to run out due to a myriad of individual tool calls when making edits and repeated, duplicate command runs (e.g `pytest` followed by `pytest --cov`), a set of helpers was introduced manually to try to contain the AI's thirst for spinning in circles.

# Features built with AI
Here's what the emojis mean:
- ✅ - AI implemented the feature without a hickup,
- ✅*️ - the feature was implemented, but there were caveats, requiring minor manual changes,
- ❌ - AI failed, the quota (or my patience) ran out and I made a lot of manual changes.

See the **Comment:** for, well, comments.

## ✅ Linter & formatter on pre-commit hook
Add a linter, code formatter and type-checker with sane configurations (default, unless the current code does not pass either of the steps). Make sure that the AGENTS.md is updated with the instructions on running these tools. Add a pre-commit hook to the repository Git config that ensures the linter, formatter & type-checker runs each time the code is commited.

**Comment:** AI did pretty good, it introduced the `Any` type but it was easy to fix.

## ✅ CLI params
Add `argparse` to the CLI module. The value for the `max_results` parameter should be configurable with a default of 100. The values for `TAGS`, `HEADING` and `BODY` should be read from a file if the parameter is provided, or default to their current values if parameters are not provided.
Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

**Comment:** AI did pretty well, asked some clarifying questions and then proceeded with the implementation correctly.

## ✅*️ Frequency abstraction
Abstract frequencies returned by `analyze()` into a separate class. The class should contain a single field called `total`. `analyze()` should produce dictionaries mapping tags into these frequencies objects instead of the current `dict[str, int]`.
This change should be fairly small and localized to the @src/core.py module.
Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

**Comment:** This simple change took a long time, probably longer than doing it manually. In the end it works, but it wasted a lot of the quota.

## ✅*️ One entry point
Please combine the @src/main.py and @src/cli.py entry points into just @src/cli.py. No backwards compatibility is necessary, but make sure that all tests keep working. Update the @README.md file to reflect the new usage.

**Comment:** This trival rename/consolidation took a long time and about 10% of the quota since each instance of the `main.py` invocation in tests was done as a separate tool call. I should really read these tests and ask the AI to clean them up first.

## ✅*️ Stats result
Abstract the values returned by `analyze()` into a separate stats dataclass that represents the whole result: including `total` tasks, `done` tasks, tag frequencies, heading word frequencies and body word frequencies.
Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

**Comment:** Another trivial change that took a long time for the AI to implement and a sizable chunk of the quota.

## ✅ Extra frequencies
Add extra fields to the `Frequency` class: `simple`, `regular`, `hard`. All of these should be integers defaulting to 0.
The values for these fields computed for each tag should be based on the `gamify_exp` property. When `analyze()` considers a task that has the `gamify_exp` property set, it should check the value of that property:

- when property value is lower than 10 it is a simple task - the `simple` frequency should be incremented,
- when it is between 10 and 20 it is a regular task - the `regular` frequency should be incremented,
- and when it is more than 20 it is a hard tas - the `hard` frequency should be incremented.

By default, if `gamify_exp` is missing, assume a task is a regular task. If `gamify_exp` is of the form `(X Y)` where both `X` and `Y` are numbers, use `X` as the basis for the estimation. In all other cases, when the `gamify_exp` property isn't an integer or a `(X Y)` pair, assume the task is a regular task. For repeated tasks assume the same value for `gamify_exp` for all repetitions. In every case the `total` frequency should also be incremented for each task.

Adjust the `Frequency.__repr__()` function to properly show all frequency values.

Make sure to run the test suite and fix the issues that might have arised. It is OK to add extra tests for the new functionality.

**Comment:** Surprisingly enough, this one went very well and resulted in a working change quickly at about 15% quota usage. An especially curious aspect was that the AI tested how to access `OrgNode` properties by running a Python REPL and checking it out by itself.

## ❌ CLI switch for the top tag criteria
Add a CLI parameter called `--tasks`. The values accepted by that parameter are `simple`, `regular`, `hard` and `total`. The default is `total`. The parameter should be used for the sorting of the results of the analysis - when the user requests `--tasks hard` the results should be ordered by the `hard` frequency and `max_items` of them should be displayed.
The display should only involve the selected frequency -in the example, only the value for `hard` frequency would be shown for each tag. The display should always display just tag name and integer frequency values. For `--tasks total` only the `total` frequency should be displayed.

Make sure to adjust the README with the updated usage.
Make sure to run the test suite and fix the issues that might have been introduced.

**Comment:** The AI got fixated on the potential breaking changes and needed multiple confirmations that it is indeed OK. It computed a very large plan of action and estimated abotu 85 minutes (!) for its execution. The plan alone took 15% of the quota, but the execution was actually swift, taking about 5 minutes and extra 30% of quota (!) ending prematurely before it got to run the linter & test suite to confirm that the change actually didn't break anything. I did that manually and it was all good.

## ✅ Proper build setup
While the quota ran out I added Poetry as a build system for this project, but currently the code itself doesn't conform to the prefered CLI application layout of a Python project. Please add a `orgstats` as a package-level directory in `src/` and move the code logic to that package. Please adjust the build configuration in @pyproject.toml to build a CLI (there is a commented out stub that you can expand). Please adjust the AGENTS.md file to reflect the new project layout. Please make sure the application works as expected by running all the validation checks via `poetry run task check`, fix any issues that might have been introduced.

**Comment:** The AI did well making all the changes correctly. It made a lot fewer command calls to validate that each step works, as expected, but still halucinated the need to verify runnig the application three different styles "for backwards compatibility".

## ❌ Default help message
When no files are provided to the CLI command the usage message should be printed instead of the empty results.

**Comment:** After planning the change I figured it would take the AI longer than applying the change manually, so I aborted the plan execution.

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

**Comment:** The AI implemented the functionality pretty well, it did miss some refactoring opportunities and disabled Linter rules complaining about code complexity.

## ✅ Refactor analyze()
The `analyze()` function is fairly large and there are some opportunities for refactoring. Please move the normalized tag lists above the for loops computing the frequencties and abstract the frequency computation into a separate function called `compute_frequencies()`. The function should take the set of items to consider, a dictionary mapping items into their frequencies and a count of repetitions. Difficulty should also be passed to the function. Please remove the linter exclusion from `analyze()` and ensure that it conforms to the linter rules.
Please refactor the relevant tests to test the new function separately.

**Comment:** The AI has done a good job, doing exactly what I asked for without any extra bits.

## ✅ Skill time ranges
I'd like to compute the time ranges for all tags/words.
For that functionality, please add a new class called `TimeRange` with two fields `earliest`, `latest`. Both of these fields will be dates the tag was first and last encountered.
The values for these field will come from the tasks stated completion times. That is, for repeated tasks, take the earliest task that is in `DONE` state (`repeated_task.after == "DONE"`).
As a fallback, if a task does not have any repeats, assume the closed timestamp as the time of occurance (`task.closed`).
If closed timestamp is not available, assume the scheduled time as the time of occurance (`task.scheduled`). If that is missing too, assume the deadline time as the time of occurance (`task.deadline`). Otherwise ignore the task.
For each such occurance, the tags time range should be updated so that the `earliest` timestamp represent the earliest date encountered in the data, while the `latest` timestamp represents the latest date encountered in the data.
Do not modify the CLI output just yet.

**Comment:** The AI explored the structure of `orgparse.OrgNode` and repeated tasks ignoring the details presented on the prompt. It did a good job nontheless.

## ✅ Skill timeline
Expand the `TimeRange` class with another field called `timeline`. This timeline will be used to chart a tag's occurrence over time.
The `timeline` will be a list of all occurances of the task - the dates without the time component paired with an integer representing the count of occurances on that day. You can use a dictionary `dict[date, int]` to represent that. It makes sense to update the `TimeRange.update()` function to also maintain the occurrence list.
Make sure that the timeline's granularity is a day, so two tasks occurring on the same day at different times should both increment the same position on the timeline.
Make sure that repeated tasks are taken into account - each repeat should be reflected on the timeline.
Do not modify the CLI output just yet.

**Comment:** The AI implemented the change, while I was cleaning some slop resulting in broken test cases. The AI decided it wasn't responsible for these, so it left them as is. When asked to address the failures afterwards, it reinstituted the slop.

## ✅ Times in command output
Display the earliest, latest & most "intense" day for the top `max_results` entries for tags, heading and body.
To achieve that, update the `TimeRange.__repr__` function to find the most "intense" day (highest number of entries related to that tag on that day) and show it as part of the representation `top_day=<date>`. When there are multiple days with equal number of occurrences, select the first one. If there are no occurrences in the timeline, show `None` as the top day.
The time range results should follow the "Top tags" etc sections in the output and be limited to just the `max_results` entries, same as the top tags sections.
This will cause a lot of output to be generated, so modify the default `max_results` parameter value to 10 instead of 100.
Please add some rudimentary tests for this new CLI output, but don't bother with very complex test cases.

**Comment:** The AI took the "don't bother" part very seriously and didn't write any tests for the CLI output of the time ranges. It did add some tests for the representation of `TimeRange` though.

## ✅ CLI switch to select tags, heading and body
Add a CLI parameter called `--show` that takes either `tags`, `heading` or `body` with a default of `tags`.
This switch will control what the CLI is displaying - either top tags & time range or heading or body.
The application should compute all the values regardless of the switch (we will address that later).
In either case, both the top frequencies and time ranges should be shown.

The output should be adjusted to list each tag on a separate line with frequency, earliest and latest dates and the top day plus the count on that day.
Please don't adjust the `__repr__` functions and instead compute these values as part of the `cli.py` module for display purposes only.

**Comment:** The AI did good. No comments here.

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

**Comment:** The AI did a good job, but was flabbergasted by the format chosen for the relation display. It did notice, that we're not filtering the relations the same way as we do for frequency computation and proposed it should do that. It also had the linter complain about too many parameters to a function, so it "refactored" it by wrapping some of the params into a tuple.

## ✅*️ Relations filtering
Tag names in relations should be filtered the same way as for freequencies computations, make sure that the exclude lists are applied to the relations "cleaning" the list before displaying the values.
The `max_relations` limit should be applied after the list of relations is filtered.

**Comment:** AI is back to its old ways of running tests manually despite an explicit instruction not to do that. It is also experiencing LSP errors which it "learned" to ignore, probably taking precious quota.

## ✅*️ Configurable normalization mapping
Currently the `MAP` used by `normalize` to normalize the word names is hard-coded. Please make that value configurable and overridable via a CLI parameter called `--mapping`.
The mapping parameter should take a JSON file mapping words to other words (effectively a `dict[str, str]`). The default value should be the current `MAP` value. That value should then be passed to `analyze()` and used for the normalization logic without affecting the computation logic.

Please make sure to test this functionality and the new CLI parameter.

**Comment:** AI got a bit fixated at error handling etc, but did the job alright. It did introduce default params not to have to modify all the test cases. I sloperated that myself not changing the net slop amount it seems.

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

**Comment:** This one was a long one, but the AI aced it. At least as far as I can tell.

## ❌ Rename --tasks
Rename the `--tasks` CLI parameter to `--filter` and the values that in can take to `simple`, `regular`, `hard` and `all`. The values should determine the behaviour the same as before, only the name of the `total` value is changed to `all`. The default value for this parameter should now be `all`.

**Comment:** Somehow the AI made this into a very long and time consuming task. Exhausting the remaining 20% of quota. It was possible to continue with the plan the next day by asking the AI to carry on after the interruption.

## ❌ Update the README
Update the README file to account for the recent development.

**Comment:** Another one that was easier to do manually than let the AI fixate on putting code coverage in the description.

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

**Comment:** The AI fixated on backwards compatibility and performance gains/penalty (it considered the fact that now one third of the computation is done, but also that the user needs to compute stuff three times). In needed a lot of convincing that this is, in fact, OK.

## ✅*️ Combine exclusion lists
Combine the CLI parameters called `--exclude-*` into one parameter that accepts a single list of words. That list should be used for the tags & relations filtering. The default value should be a list containing the values from `TAGS` combined with the values from `HEADING` and `BODY` (in the case of `BODY` use the values up to and including the `""` value).
Adjust the tests accordingly.

**Comment:** AI, again, fixated on backwards compatibility despite AGENTS.md explicitly stating it's not required. It did refactor the code fine though, but didn't remove the old, no longer used constants because that would break a lot of tests. This seems to be a common pattern - it values its time like a real boy would.

## ✅*️ Default args slop
Please remove the default argument values from the `analyze()` function and adjust the tests to pass the value manually.
Using default argument vaulues is forbidden in this project.

**Comment:** It computed a sound plan of operation, but then ran out of quota to actually execute it. It was possible to resume the execution of the plan after the quota reset.

## ✅*️ Hasattr slop
Please remove the usage of `hasattr(node, atrt)` from the function `extract_timestamp()` and adjust the tests to work correctly without using `hasattr()`.
Using `hasattr()` in the logic to make writing tests easier is bad style and you should feel bad about it.

**Comment:** This went well, it did remove all the occurances of `hasattr` and fixed the tests pretty accurately. It did create extra slop by introducing `MockedEmptyTimestamp` in each file that uses mocks, which isn't ideal.

## ✅*️ Mock slop
Please remove the node mocks from the test code. Use `orgparse.node.OrgNode` and `orgparse.date.OrgDateRepeatedTask` instead of the mocks. If it makes sense for a specific test, you can create fixtures for most of the tests and load those fixtures to test againts real-life node values..
The goal is not to use any mocking in the tests.

**Comment:** The AI did a bunch of investigating, figuring out how to use `orgparse` nodes and then formulated a rather lengthy plan. It took a while to implement, but was otherwise uneventful. It took 40% of the quota (!).

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

**Comment:** The AI computed a sound plan, but then ran out of quota before it could finish implementing it. The bulk of the quota was spent on the tool calls for all the single-line edits. After the quota reset, it finished the implementation properly.

## ✅ Additional relation filter
The SCC works great, but the output produced is kinda wonky - it still produces quite a few groups.
Please add an additional CLI parameter called `--min-group-size` that takes an integer and defaults to 3.
This parameter should be used to filter out groups smaller than the threshold during display.

**Comment:** The AI proposed to rename origial `--group-threshold` parameter to something better, like `--min-group-size`. Can't argue with that. This was easier to do manually though.

## ❌ Typed tests
I enabled type checking the tests files. Please add type signatures to the test functions and ensure that the type checking passes fine for all the test files.
You can run the checks by calling `poetry run task check`.

**Comment:** This one I expected to be a lengthy one - there were 428 type errors to begin with. Fortunately, I ran out of the weekly quote before the AI got to waste all the quota. After the weekly quota reset, I executed another plan and proceeded to implementation. It took a long time and 30% of the quota, but it added types with regexes :grimacing:. It also added a lot of slop by typing stuff as `Any` that had to be manually fixed.

## ❌ Devcontainers setup
A docker container for running the agentin.

**Comment:** Since the quote ran out, I implemented this myself.

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

**Comment:** The AI did a nice job. It, correctly, noticed that `orgparse` only handles `DONE` and `TODO` states and worked around it (in tests). The code appeared to work correctly despite the fact that nothing was done to make `orgparse` recognize different states. When confronted about how this was acomplished, the AI noted that it wasn't and figured out that the code working was purely incidental (the logbook repeat state being preferred to the actual todo state of the node).

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

**Comment:** They AI was extatic about the backwards compatibility breaking possibilities and needed convincing that it's fine. It then implemented the feature pretty well, revealing exactly how broken the previous implementation was. It also made the task state counts inconsistent - counting states twice if a task wask repeated. I asked the AI to fix that issue within the same session, just to find out that the quota run out again.

## ✅*️ General stats - day histogram
I'd like to add another histogram to the analysis - this time a distribution of tasks completed on different days of the week.

For the day of week histogram:
- extend `AnalysisResult` with a new field called `task_days: Histogram`,
- take into account only the tasks in the following states: `DONE`,
- increment the histogram `values` for each occurance of the task - that includes repeated tasks too,
- use the timestamp of a task to extract the date and use `datetime.weekday()` to extract the day of week - you might need to map that value to a string representation: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, `Friday`, `Saturday`, `Sunday`,
- the timestamp should be computed the same way as was done in `extract_timestamp()`,

Display the values for week days in the CLI output. You can add that after the todo state breakdown.

**Comment:** The AI did a good job and implemented a feature that produces a result. The result however doesn't match the counts on the state histogram.

## ✅*️ Fix timestamps
Hey, when I ran the CLI on my archive it produces a histogram that sums up to a different value than the count for `DONE` tasks on the state histogram. I think the state histogram is correct, so it must be the day histogram that is off. Is it possible that some tasks do not have a timestamp at all? I.e. they are in a DONE state, but don't have any repeats or either of closed, scheduled or deadline dates?

I see that might be the case in my Archive:

```
* DONE Add "PROJECT" section to the main TODO list.
  :PROPERTIES:
  :ARCHIVE_TIME: 2012-01-22 nie 15:51
  :ARCHIVE_FILE: ~/org/refile.org
  :ARCHIVE_CATEGORY: refile
  :ARCHIVE_TODO: DONE
  :ARCHIVE_ITAGS: REFILE
  :END:
[2012-01-22 nie 15:25]
```

Can you check if orgparse returs any timestamps for this ticket and, if so, adjust the timestamp extraction algorithm to take that into account?

**Comment:** I found an example of a bad timestamp in the archive, so the AI could just focus on fixing, not debugging. This was run in the same session as the previous task, to make sure the context is rich and the AI did well. The code still returns inconsistent results. It also introduced a bit of slop.

## ✅*️ Final timestamp fallback
Hey, I found another task that doesn't have a date in the body. It does have an `ARCHIVE_TIME` property, but that's not always given (some tasks do not end up in the Archive) and also this isn't a timestamp indicating the time the ticket was done. Here's an example of such a task:

```
* DONE Add .gitignore.                                     :COMP:maintenance:
  :PROPERTIES:
  :ARCHIVE_TIME: 2012-01-24 wto 19:50
  :ARCHIVE_FILE: ~/org/TODO
  :ARCHIVE_OLPATH: PROJECTS/Robust
  :ARCHIVE_CATEGORY: TODO
  :ARCHIVE_TODO: DONE
  :END:
```

Can you please update the `analyze()` function to increment `unknown` in the day-of-week histogram if any such tasks are found? That is, when the `extract_timestamp()` function returns nothing, that should be the incremented value. Assume a single repetition of that task (we don't have any means of determining how many repetitions there were).

**Comment:** This was also ran in the same session. It did good, but now the count is higher than the DONE state count, which indicates a problem elsewhere.

## ✅ Histogram refactor
Please refactor the usages of the `Histogram` class by adding a method `Histogram.update()` that updates a specified value by a given amount. We'd like to avoid useages like the following:

```
task_days.values["unknown"] = task_days.values.get("unknown", 0) + 1
```

**Comment:** AI did good.

## ✅ General stats - time range
I'd like to compute a global time range of all tasks completed that are in the archive.

Extend the `AnalysisResult` class with a new field called `timerange: TimeRange` which will hold the time line for all the completed tasks.

Extend the `analyze()` function to compute the over-all timerange of the tasks:
- timestamp of the earliest task,
- timestamp of the latest task,
- the general timeline - inclusive of all tasks that were completed (in the `DONE` state), including their repeats,

Only consider tasks that are in the `DONE` state. This should be analogous to the per-tag timeranges computed before, but should apply regradless of the datum used to all tasks.

Extend the CLI output to include the earliest & latest timestamps somewhere near the total tasks count.

**Comment:** The AI did well.

## ✅*️ General stats - other
I'd like to add a few more stats to the analysis results:

- average tasks completed per day (computed as the total number of tasks completed divided by the number of days between the earliest and latest task occurances globally),
- highest number of tasks completed on a single day (including the date),
- highest number of repeats of an individual task,

Some of these values can be derived from the global timeline, but for the highest number of repeats you will need to extend the `analyze()` function.

Please display these values on the CLI output right after the `Top tasks` line.

**Comment:** AI did alright. It did introduce some slop by disabling linter rules for specific functions.

## ✅*️ Linter annotations slop
I see you disabled some linter rules. Please don't do that.

- `analyze()` `PLR0912` - please refactor the function to extract the histogram computations into a separate function. Remove the linter exclusion rule.
- `main()` `PLR0912` - please refactor the function to extract the input file processing and parsing into a separate function. Remove the linter exclusion rule.
- `main()` `PLR0915` - please extract the display handling into a separate function that accepts the analysis results & configuration flags.

Update the AGENTS.md file to ensure that it explicitly prohibits disabling linter rules.

**Comment:** AI did refactor the code fine, but introduced a lot of mutation, which needs to be addressed separately.

## ✅*️ Mutation slop
Refactor the functions in `core.py` module not to use mutation as much. The `compute_*` functions can use mutation internally to update a value that is defined there and later returned, but they shouldn't mutate any values passed into the function.
Update the `analyze()` function not to define the intermediate results and instead call the `compute_*` functions to produce the values directly. It should only pass the relevant data to those functions.

Ideally, each field of the `AnalysisResults` class would be a separate call to a separate function:

```python
    tag_frequencies = compute_frquencies(nodes, ...)
    tag_relations = compute_relations(nodes, ...)
    tag_groups = compute_groups(tag_relations, ...)
    tag_time_ranges = compute_time_ranges(nodes, ...)
    task_states = compute_task_state_histogram(nodes, ...)
    task_days = compute_day_of_week_histogram(nodes, ...)
    global_timerange = compute_global_timerange(nodes, ...)
    total, max_repeat_count  = compute_task_stats(nodes, ...)
    max_single_day = compute_max_single_day(global_timerange)
    avg_tasks_per_day = compute_avg_tasks_per_day(global_timerange, total)
```

Ideally, intermediate results would be re-used as much as possible. It is OK to iterate through the list of nodes multiple times - we might want to configure `analyze()` to compute partial results in the future.

Please refactor the tests as well to match the redefined functions. If there are opportunities to simplify the tests, please go for it.

**Comment:** Expected this to take a long time and not have a great outcome. It did run out of quota, but was able to continue afterwards. It wanted to extract some helper functions, but then proceded not to use them.

## ✅*️ Treat all --done-keys equally
As you noticed previously, we are only treating `DONE` task type as locically completed. I'd like that to be changed so that all the types in `--done-keys` are treated as if the tasks were completed. To achieve that you will need to refactor the code in the core module to pass in the list of done keys and handle task todo state filtering to take those extra keys into account.

Specifically, we want the following behaviours:
- frequencies should take into account all `--done-keys`,
- time ranges (both global & per-tag) should take into account all `--done-keys`,
- tag relations should take into account all `--done-keys`,
- tag groups should be computed using the relations, so they will take the `--done-keys` into account automatically,
- average tasks completed per day should take into account all `--done-keys`,
- max completions per day should take into account all `--done-keys`,
- max repeats should take into account all `--done-keys`.

An exception to this is the state histogram - there we still want individual task states to be incremented, not a general "completed" state.

**Comment:** The AI was inclined to add a default argument to avoid having to clean up the code. It implemented the change fine, but didn't add any tests, so I asked it to do that afterwards.

## ✅*️ More task filters
I'd like to expand the filtering capabilities in `orgstats`. We will define additional CLI switches for the new filters.

There should be a way to specify multiple filters, so filter category should be a separate switch, for instance:
- `--filter-gamify-exp-above 10` - all tasks where `gamify_exp` value is above the threshold (noninclusive),
- `--filter-gamify-exp-below 20` - all tasks where `gamify_exp` value is below the threshold (noninclusive),
- `--filter-repeats-above 5` - all tasks where the number of repeats is above the threshold (noninclusive),
- `--filter-repeats-below 5` - all tasks whene the number of repeats is below the threshold (noninclusive),
- `--filter-date-from 2025-01-01` - all tasks where the timestamp comes after the specified date (noninclusive),
- `--filter-date-until 2026-01-01` - all tasks where the timestamp comes before the specified date (noninclusive),
- `--filter-property x=foo` - all tasks that have a property with a given value,
- `--filter-tag tagname` - all tasks that have a tag with a given name,
- `--filter-completed` - all tasks that have a todo state that match the values in `--done-keys`,
- `--filter-not-completed` - all tasks that have a todo state that match the values in `--todo-keys`.

The filters should be applied one by one to the list of Org Nodes before the analysis takes place. The filters should be applied in the order they appear on the command line. It is OK if the list is filtered down to zero nodes. Please detect that and adjust the CLI output to say "no results".

The old `--filter` property should be left in as a set of presets that map to the new filters:
- `--filter simple` should be mapped to `--filter-gamify-exp-below 10`,
- `--filter regular` should be mapped to `--filter-gamify-exp-above 9 --filter-gamify-exp-below 20`,
- `--filter hard` should be mapped to `--filter-gamify-exp-above 19`.

If the `gamify_exp` property is missing in a task, assume its value is 10 for the purposes of the `gamify_exp`-related filters (to retain the current logic). For the `--filter-property` filter, it should be treated as non-existed.

**Comment:** The AI wrote a lot of boilerplate to implement the feature and introduced some slop. It also didn't quite implement the features as I had in mind - my foult as the spec didn't explicitly say that.

## ❌ Filter spec slop
Can you please refactor the `FilterSpec` class to not use the `Any` type for the argument. I'd rather it had the lambda function applying the filter in there - a field called `filter` that is a function taking a list of Org Nodes and returning the filter list of OrgNodes.

Please modify `create_filter_specs_from_args()` function to add lambdas to the `FilterSpec` objects it creates (effectively combining that function with `convert_spec_to_function()`). Modify `build_filter_chain()` function to take that into account .

In `main()` you can then produce the list of `FilterSpec`s and run this code for each: `filtered_nodes = spec.filter(filtered_nodes)`.

The goal is to avoid having the `Any` typed field in `FilterSpec` and instead use the filter arguments directly in the context of the lambda.

You can re-use the `filter_*` functions, but please refactor them to use list comprehensions instead of `for` loops with `list.append()`.

The `filter_completed` and `filter_not_completed` should also be updated to take repeated tasks into account - it's OK that not all the occurances match the filter. We will address that at some point.

**Comment:** The AI made the changes, but introduced alternative slop in the process. Required a manual intervention.

## ❌ Inclusive dates
Make the `--filter-date-from` and `--filter-date-until` inclusive, makes more sense this way.

**Comment:** This was simpler to do manually.

## ❌ Filters applied consistently to repeats
Currently filters are applied to the org task list before analysis, but some of them (date, completed/not completed) let in all the repeats if any of them matches the filter, resulting in some data outside of the requested range making its way into the analysis.

This can be addressed by stripping the non-matching repeats from the tasks, or by "hydrating" the tasks in advance not to have any repeats and instead duplicating the original node instance. I think the former is better, but I'd like your opinion on that.

If you deem filtering the repeats as viable, please extend the `filter_date_from`, `filter_date_until`, `filter_completed` and `filter_not_completed` functions in the core module to also filter out the repeated tasks of a node. That is, after the filter is applied:
- if none of the reapeated tasks match, the whole node is filtered out,
- if some of the repeated tasks match, the node is replaced with a copy, that has the `repeated_tasks` property filtered to just the matching repeats,
- if all of the repeated tasks match, the node is left untouched.

Once done, you can remove the FIXME comments. Please make sure to test this thoroughly.

**Comment:** It was implemented, but the date filters were pretty sloppy and needed manual intervention. Then I noticed that date handling in general needs work.

## ✅ Accept dates with time component in ISO format (UTC-time)
Currently, the CLI accepts timestamps in a simple `YYYY-MM-DD`. I'd like to extend that so that the CLI accepts dates in the following formats:

```
YYYY-MM-DD
YYYY-MM-DDThh:mm
YYYY-MM-DDThh:mm:ss
YYYY-MM-DD hh:mm
YYYY-MM-DD hh:mm:ss
```

The last two formats have a space in them, but assume the argument is passed by the shell in quotes, so that the app only has to worry about the format parsing. It might be useful to use Python's `dateutil.parse` function as it is OK to accept even more formats.

**Comment:** This was done correctly.

## ✅ Improve cli.py test coverage
The test coverage fell well under 90%, please improve that by introducing more tests for the @src/orgstats/cli.py file.

**Comment:** This was done correctly, but inflated the test runtime significantly. There were some hickups with a subagent call (missing permissions in opencode.json likely).

## ✅*️ Timeline ASCII plots
I'd like to extend the CLI data display to include ASCII charts for time lines.

The timeline display should show up as a barchart containing `N` bars representing date buckets. Each buckets height should depend on the sum of frequencties of tasks in that bucket. Each bucket will represent 1/N of the total time range:

- If the timeline has more than N days, group the timeline activity into N buckets of equal sizes summing the occurances per bucket.
- If the timeline has fewer than 50 days, plot only as many buckets as makes sense.

Make sure to take into account all days, even those with no tag activity on that day. These should have a value of 0. You should first expand the timeline with the missing days of no activity, then group them into the N buckets and compute sums of activity per bucket. Plot the resulting sums within buckets.

I'd like the number of buckets to be configurable, with a default of 50. You can add a new CLI parameter for that called `--buckets`.

The plot will be an ASCII barchart where each bar is sized relative to the top value of the bucket - i.e. if there's a bucket with a value of 23, then that would be the 100% and all the other bar heights should be adjusted to be relative to that.

You can use the following unicode characters in the output to represent the activity bars heights:
- " " (space) - 0%
- ▁ - under 25%
- ▂ - under 37.5%
- ▃ - under 50%
- ▄ - under 62%
- ▅ - under 75%
- ▆ - under 87.5%
- ▇ - under 100%
- █ - 100%

The plot itself should look something like this:
```
|        ▁▂        ▅▃█  ▁           ▅▇   ▁▂▁       | 0
<start date>                              <end date>
```

Each bucket shows a bar sized according to the sum of activity in that bucket scaled in relation to the highest value in any bucket on the plot. Some of these buckets will be empty and others and that is OK. The plot is delineated with `|` on either side and to the right of the plot the value of the top bucket is shown. Under the chart there should be the start & end timestamps of the timeline, aligned to the either side of the plot.

Here are some more examples:

No activity during the timeline:
```
|                                                  | 0
<start date>                              <end date>
```

All days equal in activity:
```
|██████████████████████████████████████████████████| 0
<start date>                              <end date>
```

Please update the CLI output to add these plots for the global timeline and the per-tag timelines. The global plot should be place in the "Top tasks" section, which will now look like this:

```
Total tasks: 15
Average tasks completed per day: 2.00
Max tasks completed on a single day: 7
Max repeats of a single task: 2

Activity:

|        ▁▂        ▅▃█  ▁           ▅▇   ▁▂▁       | 7
2023-11-14                                2023-11-15
```

The per-tag section "Top tags" should look like this:

```
Top tags:
  erlang (2)

    |        ▁▂        ▅▃█  ▁           ▅▇   ▁▂▁       | 7
    2023-11-14                                2023-11-15

    redis (1)
    debugging (1)

  redis: (5)

    |        ▁▂        ▅▃█  ▁           ▅▇   ▁▂▁       | 7
    2023-11-14                                2023-11-15

    erlang (1)
    ...
```

**Comment:** I fully expected this to not work great, but it did implement it alright. It skipped the requirement that if the timeline has fewer than `--buckets` elements it should be shortened, etc. Needs to be addressed separately.

## ✅*️ Plot improvements - underline
Looks like the plots will need an underline to make it apparent where they begin. Please update the plot display to look like this instead:


```
2023-11-14                                 2023-11-15
┊         ▁▂        ▅▃█  ▁           ▅▇   ▁▂▁       ┊ 7
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

The dates should be moved above the chart and the underline should be composed from `┊` and `‾` characters.

**Comment:** AI decided to extend the underline under the number, which needed adjustment with another prompt. And then another, and then another.

## ✅ Plot improvements - top day
Replace the max bucket value on the plots with the top day from the timeline
```
2023-11-14                                 2024-11-15
┊         ▁▂        ▅▃█  ▁           ▅▇   ▁▂▁       ┊ 11 (2023-03-26)
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

The value should be taken from the timeline, the same way as the current display for `top_day` is generated. The date should come afterwards in parentheses.

**Comment:** This was easy enough.

## ✅ Plot improvements - Total tasks
Let's change the total tasks section to look like this:

```
2011-11-18                                2026-02-05
┊▂▂▁▁▁▁▁▁▂▂▂▂▂▂▃▁▁▁▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ▂█▅▅▆▅▅▄▃▂▁┊ 11 (2023-03-26)
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
Total tasks: 15
Average tasks completed per day: 2.00
Max tasks completed on a single day: 11
Max repeats of a single task: 2
```

The chart should come above the "Total tasks" line. All "general" stats should be at the same indent level. The logic for these values should stay the same, only the update should be updated.

**Comment:** This was also pretty easy.

## ✅ Plot improvements - per-tag sections
Let's change the per-tag display of the `Top tags:` section so that each tag section looks like this:

```
  2011-11-18                                2026-02-05
  ┊▂▂▁▁▁▁▁▁▂▂▂▂▂▂▃▁▁▁▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ▂█▅▅▆▅▅▄▃▂▁┊ 11 (2023-03-26)
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  devops (2481)
    Top relations:
      ansible (46)
      erlang (38)
      otp (36)
```
The chart for the tag is above the tag name, followed by the tag (same indent level) and its relations (extra indent level).
We will add more stats to this section at a later point.

Consecutive tag sections should be separated by a blank line:

```
Top tags
  <tag section>

  <tag section>

  ...
```
**Comment:** Also very easy.

## ✅*️ Plot improvements - start/end dates
When `--filter-date-from` and/or `--filter-date-until` are provided explicitly, all the plot charts should span this whole timerange. Adjust the code that renders a plot to accept those optional values and use those instead of the timeline's own start/end dates. The intention is to display plots that start on `args.filter_date_from or timeline.earliest` and end on `args.filter_date_until or timeline.latest`.

This should apply to both the global section plots and the per-tag plots, but it should only affect the display of the data. It should not affect how the timelines are computed.

**Comment:** Implemented correctly, but it turns out that the earlier `deepcopy()` addition causes a significant performance degradation.

## ✅ filter_node_repeats performance optimization
The `deepcopy()` introduced to get repeated task filtering implemented indeed resulted in a significant performance degradation when using multiple date/completion filters. I'd like to explore some options to not mutate the Node list, but still filter out the repeated_tasks.

Please create a simple class `FilteredOrgNode` that inherits the `class orgparse.node.OrgNode` class, takes the original node as one of the parameters and the filtered repeats as another, and delegates all method calls to the original node, except the `repeated_tasks` which it replaces with the passed in value.

Update the `_filter_node_repeats()` function to return a `FilteredOrgNode` instance instead of performing a deep-copy.

Please don't adjust any tests yet, let's first check if it helps with the performance.

**Comment:** AI implemented the extra class and adjusted the code. I did do some manual cleanup, but that was unneccesary.

## ✅ Perf optimiztion tests
Please add some tests for the newly implemented performance optimization. Focuse on the functionality, not the performance.
Please add a `NOTE` comment to the usages of `_FilteredOrgNode` indicating that this is a performance optimization.

**Comment:** This was pretty easy, but the AI went overboard with the NOTE comments, so I reworded and removed the overzelous ones.

## ✅*️ Histogram ASCII plots
I'd like to add the display for histograms now. These will be handled in a similar fashion to the activity plots, except the format will be different.

The chart will be sideways, displaying values left to right. Bar lengths should be relative to the sum of all the values in the histogram, not the highest single value in the histogram.
The names of the categories should be on the left, left-justified with a line at the tenth column. If a name of the category would overflow, please shorten it and add a dot at the end (`very long name` becomes `very long.┊`). To the right of the line the bars should be displayed, use the "█" for each segment. The 100% value should span `--blocks`, but the bar lenghts should be computed to be relative to the sum of all histogram values:
```
Task completion by day of week:
  Monday   ┊████████████ 3526
  Tuesday  ┊██████████ 3273
  Wednesday┊█████████ 3129
  Thursday ┊████████ 2936
  Friday   ┊██████ 2694
  Saturday ┊███████████ 3452
  Sunday   ┊███████████████ 4165
  unknown  ┊█ 54
```
Here's more examples:

```
Empty histogram:
  Some     ┊ 0
  Value    ┊ 0
  unknown  ┊ 0

One value at 100% histogram:
  Some     ┊ 0
  Value    ┊████████████████████████████████████████ 100

All values equal:
  Some     ┊████████████████████ 50
  Value    ┊████████████████████ 50
```

Please update the CLI output to show the task-state and day-of-week histograms as described above.

**Comment:** The AI asked for clarification on the ordering of items on the histogram, but then promptly ignored it and did its own thing.

## ✅ Date filters
The date filters `--filter-date*` should not check for completion state, instead the user will combine that with `--filter-completed` and `--done-keys`. Please adjust the implementation and tests so that both `--filter-date-after` and `--filter-date-until` are only checking for dates, not completion state.

**Comment:** Quota run out, but it carried on after it reset. Worked fine.

## ✅*️ Remove normalization from the tags, just normalize words in the heading & body
Please remove normalization from the tags, only the words in the heading & the body should be normalized. The tags should still be subject to the mapping. You can accomplish that by modifying the `_extract_items()` logic when the `category` is `tags`.
No need to modify the default exclude lists. The default `MAP` value might require some changes. The tags are usually in `CamelCase` but the normalization converts that to `lowercase`, so you might need to update the `MAP` entries to `CamelCase`. Tags usually do not have any special characters, but if there are any it is OK to leave them in.

Please update the tests to make sure that `CamelCase` tags are mapped and otherwise left undisturbed.

**Comment:** The AI cut corners again - left the old mapping values in so that fewer tests would break. Required some manual changes & extra proomptin'.

## ❌ Default lists update
I updated the default values for the exclude lists & the mapping list, and made sure that those exclusion items are case-sensitive. Please update the tests to pass using the new defaults. Ideally, the tests would be made independent of the implicit default values.

**Comment:** Just 4 tests were not passing after the manual change, so this was quicker to do manually.

## ❌ Split tag display on case
For the final display whenever a tag value is displayed, please split the word by letter case, but only if the resulting sub-words would be longer than 1 character. Here are some examples:

```
"Compilers" -> "Compilers"
"PLDesign" -> "PL" "Design"
"ProgrammingLanguageDesign" -> "Programming" "Language" "Design"
"ComputerArchitectures" -> "Computer" "Architectures"
"3DModeling" -> "3D" "Modeling"
"C++" -> "C++"
"C" -> "C"
"OTP" -> "OTP"
"HTML" -> "HTML"
"OpenSCAD" -> "Open" "SCAD"
```

**Comment:** Decided not to do it, since it already looks fine with the CamelCase tags.

## ✅*️ Group timelines
Please extend the `Group` class to add a `time_range: TimeRange` field. This field will represent the shared timeline of a group of tags.

Please update the `analyze()` function to use the `tag_time_ranges` intermediate result to compute the shared time-range of the tags in each group of `tag_groups`. You should pass that intermediate `tag_time_ranges` value to the `compute_groups()` function.

Add a new function `_combine_time_ranges()` that will take the tag time ranges and a list of tags and return a single `TimeRange` object that combines the time ranges of the tags from the list. To combine the time ranges:
- combine the `earliest` property to mean the earliest of all the time ranges of each tag from the list,
- combine the `latest` property to mean the latest of all the time ranges of each tag from the list,
- combine the `timeline` property to merge the dates & frequencies; make sure that if multiple tags from the group have occuranceson the same date, they should be summed in the resulting timeline.

Update the `compute_groups()` function to compute the shared timeline of each group.

Please update the CLI output to include the plot of the group timeline. I'd like the CLI output for the `Top groups:` to look like this:

```
Tag groups:
  <group section>

  <group section>

  ...
```

That is, each group section is indented and separated by a blank line, with individual group sections looking like this:

```
  2011-10-30                                2026-02-14
  ┊          ▁▅▃▆█▂▃▂▂ ▁▁▁▁ ▁▂ ▁ ▁▁▁ ▁▁▁▁▁▁▁▁▁ ▁▁▁▁▁▁┊ 3 (2019-06-10)
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
  Cowboy, Debugging, Erlang, OTP, Scala, Testing
```

It should be similar to the per-tag display, except the plot is followed by the group's tags.

**Comment:** The AI got a bit flabbergasted at forward-reference errors when adding a TimeRange to the Group which is defined before TimeRange. It "solved" the issue by importing annotations from the future (:shrug:) instead of by reordering the classes. :shrug:

## ✅ GitHub workflow for PR-based development
Please add a GitHub actions workflow file that will run the check command on each PR & merge.

**Comment:** No comments here.

## Code reorg
Move the filters to filters.py
Move the analysis to analyze.py
Move the plot display generation to plot.py
Move the histogram display generation to histogram.py
Remove the main.py module

## Update AGENTS.md and README.md

## Output colors

## Per-tag stats
- Total tasks
- Average tasks completed per day
- Max tasks completed on a sigle day + date
- Max repeats of a single task + truncated heading
- Top relations

Not to be shown on analyze commands output?
- State histogram
- Day of week histogram
- Category histogram

## Even more filters
- `--filter-heading term` - task must contain `term` in the filter,
- `--filter-body term` - task must contain `term` in the body,

## Per-file processing
Process each file separately, combine results at the end before displaying stuff, preserving the file origin for each task

## Another attempt at a fix for task states counts
Now the counts for day of week histogram are higher than the total count of done tasks. Likely, now it's the done task count that's wrong.

## Dedicated analysis command
Wrap the current analysis logic into a dedicated `analyze` command. There will be more commands to come.

The CLI arguments should be divided into global & per-command options. Global arguments should be:
- `--mapping`,
- `--exclude`,
- `--max-results`,
- `--help`,
- `--filter-*`,
- `FILE`

The rest should be accepted by the `analyze` command.
I want these global arguments to be usable after the command name, i.e. the accepted invocation should be:

```bash
orgstats analyze -n 5 examples/ARCHIVE_small
```

## Dedicated search command
Add an extra `search` command that allows searching for specific tag occurances and shows statistics of tasks that are tagged with the specified tag.

The invocation should look like this:

```bash
orgstats search tagname
```

The comand should search for the occurance of specified tag in either the tags, heading or the task body. Add a new CLI parameter called `--in` that takes one of the following values: `tags`, `heading`, `body`. The following logic should apply:
- for `tags` the specified tag is search for in Org Node's tags, subject to the filter & mapping lists,
- for `heading` the specified tag value, case-sensitive, is searched for in the Org Node's heading contents (string search),
- for `body` the specified tag value, case-sensitive, is searched for in the Org Node's body contents (string search),
The default value for this switch should be `tags`. This switch should be a command switch, not global.

Once suitable tasks are found, the command should compute the analysis results much like `analyze` does.

The command should respect any additional filters passed by the `--filter*` flags. In fact, the comands search logic can be implemented as a filter in itself.

The command should display the following information:
- A header stating that these are the results for a specific search term,
- General statistics of the tasks containing the searched term,
- State distribution,
- Day distribution,
- Time range of tasks with the specific tag present,
- Top relations for this tag (respecting the `--max-relations` flag),
- Top groups for this tag (respecting the `--min-group-size` flag),
- A list of tasks with this tag ordered by their timestamp (most recent at the top, respecting the `--max-results` flag),

The output will be fairly similar to the `analyze` output, with the caveat that the `Top tags` section would be replaced with search-term-specific relations & time range.

I expect that groups won't be very useful, so don't bother testing the output of these just yet. We might remove them from the output.

List the tasks headings and the files where these can be found.

## Better heading & body parsing

## Output abstraction
We will be adding more output options, for instance JSON output, visualization output, etc.

## Graphviz/Dot output

## D3 visualization - tag cloud

## D3 visualization - relations graph
Node size is how many tasks are related to a tag. Closeness is how related these are.

## D3 visualization - tag charts over time
Allow selecting specific tags or top tags.

