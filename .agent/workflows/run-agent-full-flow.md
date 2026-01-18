---
description: Run the Depp Scraper agent flow
---

Use this workflow when the user needs to run the entire workflow to test if the agent can generate a working script and test it.

Make sure everything is set up to start testing the Script Builder Agent.
1. Make sure the MCP Server is running
2. Make sure the Backend is running
3. No need for the frontend to be running, only the backend and MCP Server is needed.

After this, execute the agent with the data to test it. These are some examples of counties you can use to test it

Brevard County: 
URL = https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName
Search term = Lauren Homes
Date from = 01/01/1980
Date to = 01/06/2026

Flagler County: 
URL = https://records.flaglerclerk.com/
Search term = ESSEX HOME MORTGAGE SERVICING CORP 
Date from = 01/01/1992 
Date to = 12/31/1992

Dallas County: 
URL = https://dallas.tx.publicsearch.us/
Search term = LA FITTE INV INC
Date from = 01/01/1978 
Date to = 12/31/1978

For the test to be successful, the agent should generate a script and run it successfully. When running the script, the successfull output should be a csv file with the data extracted from the website. If that doesnt happen, then you need to investigate why it failed, add temporary logging to the agent/script-template/anywhere you see fit to help you debug it, and then try again.