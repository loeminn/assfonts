# Log queue regression tests

These tests compile the production queue without the font/Qt dependencies:

```sh
cmake -S tests -B build/queue-tests -DCMAKE_BUILD_TYPE=Release
cmake --build build/queue-tests
ctest --test-dir build/queue-tests --output-on-failure
```

The test drains completed queues and races 16 concurrent producers against a
consumer for 1,000 rounds. It checks empty completion, FIFO order, delivery of
the final message, and termination. CTest's timeout catches stuck waiters.

For race detection, configure with `-DCMAKE_CXX_FLAGS="-fsanitize=thread -g"`
and `-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=thread` on a supported Linux host.

The original v0.7.3 completion callback wrote `is_finished` without acquiring
the consumer's mutex. Besides a data race, a notification could land between
the predicate check and the wait, leaving the CLI stuck after processing.
All queue state now uses one mutex; completion also drains any pending logs.
This fixes a source-level defect, but does not establish the cause of every
reported subtitle timeout.
