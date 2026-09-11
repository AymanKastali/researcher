/* quiz.js — immediate feedback for retrieval practice.
 *
 * Vanilla JavaScript, no dependencies, no network. It progressively enhances
 * plain markup: with this file absent or JavaScript disabled, a quiz is still a
 * question followed by a readable list of answers and its explanation. Nothing
 * here is required to read a lesson — only to be told whether you were right.
 *
 * Expected markup (classes come from lesson.css):
 *
 *   <div class="quiz">
 *     <span class="label">Check yourself</span>
 *     <p class="quiz-question">...</p>
 *     <ul class="quiz-answers">
 *       <li><button class="quiz-answer" type="button">...</button></li>
 *       <li><button class="quiz-answer" type="button" data-correct>...</button></li>
 *     </ul>
 *     <p class="quiz-explanation">...</p>   <!-- optional -->
 *   </div>
 *
 * Mark the correct answer with `data-correct`. Each quiz on a page is wired
 * independently: answering one leaves the others untouched.
 *
 * Answers are written to the same length on purpose -- the lesson must not leak
 * which one is right through its shape -- so this file never writes into an
 * answer box. Feedback goes in its own element below the list.
 */

(function () {
  "use strict";

  var CORRECT_MESSAGE = "Correct.";
  var INCORRECT_MESSAGE = "Not quite. The correct answer is marked above.";

  function feedbackElementFor(quiz) {
    var existing = quiz.querySelector(".quiz-feedback");
    if (existing) {
      return existing;
    }

    var feedback = document.createElement("p");
    feedback.className = "quiz-feedback";
    /* Announced to a screen reader the moment it is filled in. */
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");

    var explanation = quiz.querySelector(".quiz-explanation");
    if (explanation) {
      quiz.insertBefore(feedback, explanation);
    } else {
      quiz.appendChild(feedback);
    }
    return feedback;
  }

  function setUpQuiz(quiz) {
    var answers = Array.prototype.slice.call(
      quiz.querySelectorAll(".quiz-answer")
    );
    if (answers.length === 0) {
      return;
    }

    /* Marks this widget as live, which is what lets the stylesheet hide the
     * explanation until it has been earned. */
    quiz.classList.add("is-enhanced");

    var explanation = quiz.querySelector(".quiz-explanation");
    if (explanation) {
      explanation.hidden = true;
    }

    var feedback = feedbackElementFor(quiz);

    function answer(chosen) {
      var wasCorrect = chosen.hasAttribute("data-correct");

      answers.forEach(function (candidate) {
        candidate.disabled = true;
        candidate.setAttribute("aria-disabled", "true");

        if (candidate === chosen) {
          candidate.classList.add(wasCorrect ? "is-correct" : "is-incorrect");
        } else if (!wasCorrect && candidate.hasAttribute("data-correct")) {
          /* Show where the right answer was: being told only "wrong" teaches
           * nothing. */
          candidate.classList.add("is-correct");
        }
      });

      feedback.textContent = wasCorrect ? CORRECT_MESSAGE : INCORRECT_MESSAGE;
      feedback.classList.add(wasCorrect ? "is-correct" : "is-incorrect");

      if (explanation) {
        explanation.hidden = false;
      }
    }

    answers.forEach(function (candidate) {
      candidate.addEventListener("click", function () {
        if (candidate.disabled) {
          return;
        }
        answer(candidate);
      });
    });
  }

  function setUpAllQuizzes() {
    Array.prototype.forEach.call(document.querySelectorAll(".quiz"), setUpQuiz);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setUpAllQuizzes);
  } else {
    setUpAllQuizzes();
  }
})();
