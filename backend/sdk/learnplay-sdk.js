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
    levelComplete: function (level, totalLevels) {
      emit("level_complete", {
        level: Number(level) || 0,
        totalLevels: Number(totalLevels) || 0,
      });
    },
    /** Report how far a learner has gotten (solved stages / total). */
    progress: function (opts) {
      opts = opts || {};
      var level = Number(opts.level) || 0;
      var total = Number(opts.totalLevels || opts.total) || 0;
      var percent =
        opts.percent != null
          ? Number(opts.percent)
          : total > 0
            ? Math.round((level / total) * 100)
            : 0;
      emit("level_complete", {
        level: level,
        totalLevels: total,
        percent: percent,
        solved: !!opts.solved,
      });
    },
    /** Named checkpoint inside a game (concept, badge, stage id). */
    milestone: function (opts) {
      opts = opts || {};
      emit("milestone", {
        id: opts.id || "",
        label: opts.label || "",
        level: Number(opts.level) || 0,
        totalLevels: Number(opts.totalLevels || opts.total) || 0,
      });
    },
  };

  global.LearnPlay = LearnPlay;
})(typeof window !== "undefined" ? window : globalThis);
