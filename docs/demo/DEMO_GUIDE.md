# CodeGuard AI — Semester Project Demo Guide

## Prepare

1. Start Docker Desktop and confirm the Linux engine is ready.
2. In VS Code, open `C:\codex` and start the app:

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run frontend/app.py
   ```

3. Open the local Streamlit URL printed in the terminal.

## Demonstrate manual evaluation

1. In **New evaluation**, choose **Manual paste**.
2. Enter a question such as “Write a function that adds two numbers.”
3. Set **Model/source label** to `Demo model A`.
4. Paste a response containing a ` ```python ` block and explanation prose, then submit.
5. Repeat for the same question, using `Demo model B` and a second sample response.
6. Open **Explanation analysis**. Show claim status, retrieved passage, Python documentation link, similarity value, and the reason. Try “Python lists are mutable.” and “Python tuples are mutable.” to show the narrow supported and contradicted examples.
7. Open **Model comparison** to compare the two records for the same prompt. Explain that absent test/performance rows are shown as not run/unavailable, not as zero.

## Demonstrate tests and sandbox

1. In **Test cases**, select an evaluation with a simple function.
2. Use harmless JSON cases such as `[2, 3]` → `5` and `[-2, 5]` → `3`.
3. In **Isolated run**, run a harmless print or arithmetic example and review separately labeled timings and whole-container memory.
4. State clearly that container startup and Docker overhead are not algorithm runtime, and the Docker setup is not a production-grade public sandbox.

## Demonstrate a reliability report

1. Open **Reliability report** and select an evaluation.
2. Review the prompt, model/source, extracted code and static findings, test results, performance rows, explanation claims and evidence, plus limitations.
3. Download the JSON. Point out that the system reports component observations without inventing a single reliability score.

## Optional API path

If an API key is configured in the app process environment, select **OpenAI API** in **New evaluation** or request another response in **Model comparison**. Choose a model name, then explain that the request may incur charges. Do not show the API key during the demo. Without a key, complete the entire demo using manual mode.

## Suggested closing explanation

CodeGuard is a student MVP that gathers evidence about code and explanations. Static checks, small manual tests, isolated execution, measured resource observations, and a small evidence corpus each cover only part of reliability. A status is not a guarantee, and “Insufficient evidence” does not mean “false.”
