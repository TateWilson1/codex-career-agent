# Privacy

All personal records, original resumes, generated documents, databases, browser state, tokens, and confirmations belong under the ignored `user-data/` tree or another directory selected with `JOB_AGENT_DATA`. Public fixtures use fictional identities and reserved domains.

Before publishing or committing, ask Codex to perform the privacy check. Codex runs `job-agent doctor` and inspects Git state internally. The doctor checks ignore rules, likely tracked private artifacts, configuration, and database access. It cannot prove that free text contains no personal information, that Git history is clean, or that the local computer is secure.
