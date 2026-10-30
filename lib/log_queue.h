// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef ASSFONTS_LOG_QUEUE_H_
#define ASSFONTS_LOG_QUEUE_H_

#include <condition_variable>
#include <mutex>
#include <queue>
#include <utility>

namespace ass {

// One producer per subtitle. Finish is called after its final log message.
// The completion flag and messages share the waiter's mutex: notifying without
// this lock can race between checking the predicate and entering the wait.
template <typename T>
class LogQueue {
 public:
  void Push(T value) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      messages_.push(std::move(value));
    }
    ready_.notify_one();
  }

  void Finish() {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      finished_ = true;
    }
    ready_.notify_all();
  }

  bool Pop(T& value) {
    std::unique_lock<std::mutex> lock(mutex_);
    ready_.wait(lock, [&] { return finished_ || !messages_.empty(); });
    if (messages_.empty()) return false;
    value = std::move(messages_.front());
    messages_.pop();
    return true;
  }

 private:
  std::mutex mutex_;
  std::condition_variable ready_;
  std::queue<T> messages_;
  bool finished_ = false;
};

}  // namespace ass

#endif  // ASSFONTS_LOG_QUEUE_H_
