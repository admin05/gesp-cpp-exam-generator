# Programming Sample Verification

The final mixed paper:

`docs/GESP四级偏上五级入门模拟卷2_10选4编程_样例已校验.docx`

contains 4 programming problems, each with 5 sample tests.

The script:

`scripts/make_gesp_style_paper_v2_verified.py`

does not rely on manually typed outputs for these programming samples. Instead,
each problem has a solver function:

- `solve_row_col`
- `solve_prime_count`
- `solve_tasks`
- `solve_longest_rise`

During document generation, every sample input is passed to its solver function,
and the computed output is inserted into the Word table.

Additional verification was run after generation by recomputing all 20 outputs.
All samples matched.

