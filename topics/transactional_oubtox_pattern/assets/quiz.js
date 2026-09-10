/* ---------------------------------------------------------------------------
   quiz.js — reusable interactive components for lessons in this workspace.

   Two components, both progressive-enhancement over plain markup (the page is
   still readable and printable with JS off).

   1. Quiz — retrieval practice with immediate, per-choice feedback.

      <div class="quiz">
        <ol>
          <li class="q" data-answer="b">
            <p class="q-text">Question?</p>
            <ul class="options">
              <li><button data-opt="a">First option</button></li>
              <li><button data-opt="b">Second option</button></li>
            </ul>
            <div class="feedback" data-for="a">Why that one is wrong.</div>
            <div class="feedback" data-for="b">Why that one is right.</div>
          </li>
        </ol>
      </div>

      One attempt per question, on purpose: guessing until the button turns
      green is recognition, not recall. After the attempt the correct option is
      marked and the feedback for the CHOSEN option is revealed, so a wrong
      answer teaches something specific rather than just being wrong.

   2. Recall card — free-recall prompt with a hidden answer.

      <div class="recall">
        <p class="prompt">Say it out loud, then check.</p>
        <button class="reveal">Reveal</button>
        <div class="answer">…the model answer…</div>
      </div>
   --------------------------------------------------------------------------- */

(function () {
  "use strict";

  function initQuiz(quiz) {
    var questions = quiz.querySelectorAll(".q");
    var answered = 0;
    var correct = 0;

    var score = document.createElement("p");
    score.className = "quiz-score";
    score.textContent = "0 of " + questions.length + " answered";
    quiz.appendChild(score);

    Array.prototype.forEach.call(questions, function (q) {
      var right = q.getAttribute("data-answer");
      var buttons = q.querySelectorAll(".options button");

      Array.prototype.forEach.call(buttons, function (btn) {
        btn.addEventListener("click", function () {
          var chosen = btn.getAttribute("data-opt");
          var wasRight = chosen === right;

          // Lock the question — one attempt only.
          Array.prototype.forEach.call(buttons, function (b) {
            b.disabled = true;
            if (b.getAttribute("data-opt") === right && b !== btn) {
              b.classList.add("reveal-right");
            }
          });
          btn.classList.add(wasRight ? "chosen-right" : "chosen-wrong");

          var fb = q.querySelector('.feedback[data-for="' + chosen + '"]');
          if (fb) fb.classList.add("shown");

          answered += 1;
          if (wasRight) correct += 1;
          score.textContent =
            answered + " of " + questions.length + " answered · " +
            correct + " correct";
        });
      });
    });
  }

  function initRecall(card) {
    var btn = card.querySelector("button.reveal");
    var answer = card.querySelector(".answer");
    if (!btn || !answer) return;
    btn.addEventListener("click", function () {
      answer.classList.add("shown");
      btn.remove();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll(".quiz"), initQuiz);
    Array.prototype.forEach.call(document.querySelectorAll(".recall"), initRecall);
  });
})();
