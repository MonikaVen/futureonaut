(function (global) {
  "use strict";

  var taskStarts = {};
  var sessionStart = Date.now();

  function emit(type, payload) {
    var message = {
      source: "learnplay-sdk",
      type: type,
      payload: payload || {},
      ts: Date.now(),
    };
    try {
      if (global.parent && global.parent !== global) {
        global.parent.postMessage(message, "*");
      }
    } catch (e) {
      /* ignore */
    }
    try {
      global.dispatchEvent(new CustomEvent("learnplay:" + type, { detail: message }));
    } catch (e2) {
      /* ignore */
    }
  }

  var LearnPlay = {
    score: function (delta) {
      var value = Number(delta) || 0;
      emit("score", { delta: value });
      return value;
    },
    answer: function (opts) {
      opts = opts || {};
      var correct = !!opts.correct;
      emit("answer", {
        correct: correct,
        taskId: opts.taskId || null,
        points: opts.points || 0,
      });
      if (opts.points) {
        emit("score", { delta: correct ? Number(opts.points) : 0 });
      }
      return correct;
    },
    taskStart: function (taskId) {
      var id = taskId || "default";
      taskStarts[id] = Date.now();
      emit("task_time", { taskId: id, phase: "start" });
    },
    taskEnd: function (taskId) {
      var id = taskId || "default";
      var start = taskStarts[id] || sessionStart;
      var durationMs = Date.now() - start;
      emit("task_time", { taskId: id, phase: "end", durationMs: durationMs });
      delete taskStarts[id];
      return durationMs;
    },
    complete: function (extra) {
      emit("complete", Object.assign({ durationMs: Date.now() - sessionStart }, extra || {}));
    },
  };

  global.LearnPlay = LearnPlay;
})(typeof window !== "undefined" ? window : globalThis);
