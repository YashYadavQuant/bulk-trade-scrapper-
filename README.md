# Bulk Trades — Mobile-ready

## Use on your phone on the same Wi-Fi as your PC
1. Extract this ZIP on Windows.
2. Open PowerShell in this folder and run:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
3. In another PowerShell window run `ipconfig`; find the Wi-Fi IPv4 address, e.g. `192.168.1.5`.
4. Connect your phone to the same Wi-Fi and open `http://192.168.1.5:8501` in Chrome (replace with your PC's actual IP).
5. Allow Python through Windows Firewall on private networks if prompted. Keep the PC on.

## Use anywhere
Deploy to Streamlit Community Cloud: https://share.streamlit.io/
Push this folder to GitHub, choose the repo and branch, set main file to `app.py`, then deploy. Open the resulting HTTPS URL on your phone.

Official data sources:
- NSE: https://www.nseindia.com/report-detail/display-bulk-and-block-deals
- BSE: https://www.bseindia.com/markets/equity/EQReports/BulknBlockDeals.aspx

Automated endpoints may block requests or change formats; upload official CSV reports if fetching fails. The dashboard is responsive, but it still requires a running host (PC or cloud) and does not run as an offline native Android app. Research only, not investment advice.
