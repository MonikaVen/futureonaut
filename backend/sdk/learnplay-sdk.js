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

  var sessionClosed = false;

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
      if (sessionClosed) {
        return;
      }
      sessionClosed = true;
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
    /**
     * Report a solved stage. Pass {complete:true} when the learner finishes the game.
     * Does not mark the session solved unless complete is set (so a failed final
     * attempt can still show Level 4/5 instead of Solved).
     */
    stage: function (done, total, extra) {
      extra = extra || {};
      var level = Number(done) || 0;
      var tot = Number(total) || 0;
      this.progress({
        level: level,
        totalLevels: tot,
        percent: extra.percent,
      });
      if (extra.label || extra.id) {
        this.milestone({
          id: extra.id || String(extra.label || "stage"),
          label: extra.label || extra.id || "",
          level: level,
          totalLevels: tot,
        });
      }
      if (extra.points) {
        this.score(Number(extra.points) || 0);
      }
      if (extra.correct != null || extra.points) {
        this.answer({
          correct: extra.correct != null ? !!extra.correct : true,
          taskId: extra.id || extra.label || null,
        });
      }
      if (extra.complete) {
        this.complete({
          levelsCompleted: extra.levelsCompleted != null ? extra.levelsCompleted : level,
          totalLevels: tot,
          score: extra.score,
        });
      }
    },
  };

  global.LearnPlay = LearnPlay;
})(typeof window !== "undefined" ? window : globalThis);
