"""The machinery that runs a Game and leaves a record of it: the two-phase Submission
coordinator, the decision log a settled Game is graded against, and timing/error logging.
None of it decides a Charge or a Limit -- it moves numbers `src.pricing.engine` already
decided out to the API, and writes down why."""
