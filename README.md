# Recall-Auto
Recall automation Repo

Automated ACH Recalls 

Status: Testing Phase                                            DRI: Chintan Rout, Advik Nandakumar


BLUF:
We worked on an automated python based solution, to streamline the recall investigation process, to potentially reduce case handling time from 8 minutes to approximately 3 minutes for standard cases. Once implemented this tool can increase efficiency in ACH Recalls, thereby allowing SDC Analysts to focus on complex cases requiring deeper investigation.

Background:
The volume of recall cases has consistently been high, with each case typically requiring around 8 minutes to process through the standard workflow. This process involves multiple tools (Front, Zix, Hubble, and Google Sheets) and often relies on manual copy-pasting, which can be time-consuming. 

Solution Implementation:
We have developed an automation tool utilizing Python and Selenium that replicates the manual user process. The tool performs the following tasks:
1. Accesses Front and navigates to the "Assigned to Me" section
2. Extracts key information from each case (subject line, VBAN, amount, date)
3. Inputs extracted data into Hubble queries
4. Generates appropriate rejection responses with CU_tokens
5. Compiles outputs, including responses, Hubble query results, and email details
6. Pastes compiled information into Front emails and logs data in a CSV file

Performance:
- Happy path cases (Horizon accounts with transaction details) are processed in approximately 1 minute.
- The tool gracefully handles errors such as unextractable information from PDFs/images, invalid VBANs, or PayServer accounts.
- In error cases, the tool moves to the next case while logging available information.

User Workflow:
Agents can run this tool on a secondary machine. Once the automation completes, they can quickly validate the pasted information and send responses. This approach reduces investigation time from ~7 minutes to ~3 minutes per case while maintaining a comprehensive audit trail.

Impact:
- Significant time savings for users (estimated 20 cases per day, 70% being Horizon cases)
- Reduced manual errors (e.g., sending incorrect tokens)
- Increased bandwidth for complex cases requiring in-depth investigation
Support Required from TechOps: 
Tooling/Code Review: Before we use this script in SDC, we would like to get TechOps’s thoughts on the implementation and if any changes are needed. We can setup some time to walk through the script and discuss any change management that would be needed. 

Upcoming Workflow Changes on ACH Recalls: Currently, this script is developed for the current Front based workflow. As Engg/TechOps plans to move away from Front to other tooling, we’d love to partner on how this can be modified for the new tooling. 





Future Enhancements:
1. Improve date extraction to increase the number of Horizon cases solvable in one iteration
2. Expand investigative notes to further reduce manual effort
3. Extend functionality to handle PayServer, amendment, and beneficiary cases

Adaptability:
The underlying logic of recall resolution remains consistent even if current tools are deprecated. The code can be adapted to accommodate new tools and processes, ensuring long-term viability.


Recording:
https://stripe.zoom.us/rec/share/vZwVP-kJp4wk5SsaBvNEbKjgyYSTMwn-T7fsJ8pKwLPY4Xl5hXyD9NmkX3MPfIk-.RbAtGtDwcRzeDl-b

Passcode: 4RV&fERU

The Code:
https://git.corp.stripe.com/advikn/Recall-Auto/blob/a54a24a389a52f87762f43b5ec0d2a4f45968205/ACH%20Recall%20Automation
