# Project Log

## Initial Scope

The source teaching requirements covered:

- Variables and basic data types.
- Assignment, input, output, arithmetic, and math functions.
- Sequential, conditional, and loop structures.
- Logical expressions and ternary operator.
- One-dimensional and two-dimensional arrays.
- String operations.
- Functions, recursion, recurrence, enumeration, simulation.
- Simple sorting and searching.
- Sieve algorithms, greedy algorithms, backtracking.
- Simple probability, statistics, and logic reasoning.

## GESP Level Mapping

The overall course/exam scope maps approximately to:

- GESP C++ level 1-2 for the entry-level requirements.
- GESP C++ level 3-4 for arrays, strings, functions, recurrence, sorting, and search.
- Introductory GESP C++ level 5 for sieve, greedy, recursion, and related algorithmic topics.

Working target used in later papers:

> GESP C++ level 4 solid foundation, with level 5 introductory practice.

## Iterative Paper Generation

1. Created a 20-question advanced primary C++ choice set.
2. Increased difficulty while staying in the requested knowledge range.
3. Edited a user-provided Word file to restore missing question numbers.
4. Expanded to 50 questions and placed answers on the final page.
5. Added C++ syntax highlighting to code segments.
6. Generated a 50-question remedial paper from wrong answers.
7. Generated a second 50-question remedial paper focused on sorting, divisibility, and logic.
8. Generated a balanced comprehensive 50-question paper.
9. Built GESP-style mixed papers: 10 choice questions + 4 programming tasks.
10. Split mixed paper into separate choice-question and programming-question files.
11. Generated a 20-question remedial choice paper from student errors.
12. Generated a second mixed paper with verified programming samples.

## Verification

For generated DOCX files, checks included:

- Expected question counts.
- Expected answer-table counts.
- Presence of C++ code indentation.
- Presence of run-level syntax coloring.
- Programming sample counts.
- For the final mixed paper, all programming sample outputs were recomputed by solver functions.

DOCX image rendering was attempted via the Documents skill renderer, but failed
because `soffice` was not installed in the local environment.

