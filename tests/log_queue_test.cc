#include "../lib/log_queue.h"

#include <cstdlib>
#include <future>
#include <iostream>
#include <thread>
#include <vector>

void Check(bool ok) {
  if (!ok) std::abort();
}

int main() {
  // A worker may finish before the main thread reaches its log queue.
  ass::LogQueue<int> completed;
  completed.Push(1);
  completed.Push(2);
  completed.Finish();
  int value = 0;
  Check(completed.Pop(value) && value == 1);
  Check(completed.Pop(value) && value == 2);
  Check(!completed.Pop(value));

  // Exercise completion with no logs and immediately after the final log,
  // including multiple workers finishing while queues are drained in order.
  for (int round = 0; round < 1000; ++round) {
    std::vector<ass::LogQueue<int>> queues(16);
    std::vector<std::thread> workers;
    std::promise<void> start;
    auto gate = start.get_future().share();
    for (int i = 0; i < 16; ++i) {
      workers.emplace_back([&, i, gate] {
        gate.wait();
        for (int n = 0; n < i; ++n) {
          queues[i].Push(n);
          if ((round + n) % 2 == 0) std::this_thread::yield();
        }
        queues[i].Finish();
      });
    }
    start.set_value();
    for (int i = 0; i < 16; ++i) {
      int count = 0;
      while (queues[i].Pop(value)) Check(value == count++);
      Check(count == i);
    }
    for (auto& worker : workers) worker.join();
  }
  std::cout << "Completed 16000 queues without lost logs or stuck waiters\n";
}
