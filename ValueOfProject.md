Privacy Enhancements Added in Our Fork

We forked the original project to introduce several privacy‑focused improvements aimed at protecting user data and aligning the application with modern data‑protection regulations.

Redacted CV Processing

The original workflow sent full CVs—including personal identifiers—to an external AI service. Our fork now automatically removes sensitive information before any processing, including:
- Names
- Addresses
- Phone numbers
- Email addresses
- Other identifiable personal details

This ensures that only the minimum necessary data is ever shared with external tools.

Automatic Data Deletion

To support regulatory compliance (e.g., GDPR), we added an optional feature that automatically deletes stored user data after a configurable number of days.

- Fully configurable retention period
- Applies to all stored CV‑related data
- Helps reduce long‑term data exposure risks
