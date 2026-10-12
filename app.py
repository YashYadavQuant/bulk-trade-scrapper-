import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import date, timedelta

st.set_page_config(page_title="Bulk Trades", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
.block-container{padding:1rem .8rem 2rem;max-width:1250px}
[data-testid="stMetric"]{padding:12px;border-radius:12px;background:var(--secondary-background-color)}
@media(max-width:768px){
 .block-container{padding:.5rem .55rem 1.5rem}
 h1{font-size:1.55rem!important} h2{font-size:1.25rem!important}
 [data-testid="stMetricValue"]{font-size:1.1rem!important}
 [data-testid="stMetricLabel"]{font-size:.75rem!important}
 .stButton button,.stDownloadButton button{width:100%;min-height:2.7rem}
}
</style>
""", unsafe_allow_html=True)
st.title("📊 Bulk Trades")
st.caption("NSE + BSE · Net disclosed buying/selling · Repeat buyers · Both-side flags")

with st.expander("Filters and data upload", expanded=True):
    exchanges = st.multiselect("Exchanges", ["NSE", "BSE"], ["NSE", "BSE"])
    c1,c2 = st.columns(2)
    with c1: from_date = st.date_input("From date", date.today()-timedelta(days=7))
    with c2: to_date = st.date_input("To date", date.today())
    deal_kind = st.selectbox("Report type", ["Bulk deals", "Block deals", "Both"])
    uploads = st.file_uploader("Upload official NSE/BSE CSV report(s)", type=["csv"], accept_multiple_files=True)
    fetch = st.button("Try fetching exchange data", type="primary", use_container_width=True)

def fetch_csv(exchange, start, end, kind):
    headers={"User-Agent":"Mozilla/5.0 Chrome/131.0 Safari/537.36","Accept":"application/json,text/csv,*/*"}
    if exchange=="NSE":
        s=requests.Session(); s.headers.update(headers)
        s.get("https://www.nseindia.com",timeout=15)
        typ="bulk_deals" if kind=="Bulk deals" else "block_deals"
        url="https://www.nseindia.com/api/historicalOR/bulk-block-short-deals"
        r=s.get(url,params={"optionType":typ,"from":start.strftime("%d-%m-%Y"),"to":end.strftime("%d-%m-%Y"),"csv":"true"},timeout=30)
        r.raise_for_status()
        if not r.content or r.content.lstrip().startswith(b"<"): raise ValueError("NSE returned HTML or empty response; upload its official CSV.")
        df=pd.read_csv(BytesIO(r.content)); df["exchange"]="NSE"; df["deal_type"]=kind; return df
    url="https://api.bseindia.com/BseIndiaAPI/api/BulkDealData_ng/w"
    h={**headers,"Referer":"https://www.bseindia.com/markets/equity/EQReports/BulknBlockDeals.aspx"}
    r=requests.get(url,headers=h,params={"DealType":"1" if kind=="Bulk deals" else "2","sc_code":"","FDate":start.strftime("%d/%m/%Y"),"TDate":end.strftime("%d/%m/%Y")},timeout=30)
    r.raise_for_status()
    data=r.json()
    if isinstance(data,dict): data=next((v for v in data.values() if isinstance(v,list)),[])
    df=pd.DataFrame(data); df["exchange"]="BSE"; df["deal_type"]=kind; return df

def norm_col(x):
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in str(x)).split())
ALIASES={
"date":["date","trade date","deal date","transaction date"],
"symbol":["symbol","scrip code","scrip","security name","company","stock"],
"client":["client name","client","investor name"],
"side":["buy sell","buy/sell","buy / sell","side","transaction type","buysell"],
"qty":["quantity traded","quantity","qty","shares","traded quantity"],
"price":["trade price","price","weighted average price","wght avg price"]}
def normalize(raw):
    if raw.empty:return pd.DataFrame()
    cols={norm_col(c):c for c in raw.columns}; found={}
    for key,aliases in ALIASES.items():
        for alias in aliases:
            if norm_col(alias) in cols: found[key]=cols[norm_col(alias)];break
    if any(k not in found for k in ALIASES): return pd.DataFrame()
    d=pd.DataFrame()
    d["date"]=pd.to_datetime(raw[found["date"]],errors="coerce",dayfirst=True)
    d["symbol"]=raw[found["symbol"]].astype(str).str.strip().str.upper()
    d["client"]=raw[found["client"]].astype(str).str.strip()
    side=raw[found["side"]].astype(str).str.upper().str.strip()
    d["side"]=side.map(lambda x:"BUY" if x in ["B","BUY","PURCHASE","PURCHASED"] or "BUY" in x else ("SELL" if x in ["S","SELL","SALE","SOLD"] or "SELL" in x else "UNKNOWN"))
    for k in ["qty","price"]:
        d[k]=pd.to_numeric(raw[found[k]].astype(str).str.replace(",","",regex=False).str.replace("₹","",regex=False),errors="coerce")
    d["exchange"]=raw["exchange"].astype(str) if "exchange" in raw else "Uploaded CSV"
    d["deal_type"]=raw["deal_type"].astype(str) if "deal_type" in raw else "unknown"
    d=d.dropna(subset=["date","qty","price"])
    d=d[(d.qty>0)&(d.price>0)&d.side.isin(["BUY","SELL"])]
    d["value_cr"]=d.qty*d.price/1e7
    d["client_key"]=d.client.str.upper().str.replace(r"\s+"," ",regex=True)
    return d

frames=[]; errors=[]
if uploads:
    for f in uploads:
        try:
            x=pd.read_csv(f);x["exchange"]=f.name.split("_")[0].upper() if f.name.split("_")[0].upper() in ["NSE","BSE"] else "Uploaded CSV"
            frames.append(x)
        except Exception as e: errors.append(f"{f.name}: {e}")
if fetch:
    if from_date>to_date: st.error("From date must be on or before To date.")
    else:
        kinds=["Bulk deals","Block deals"] if deal_kind=="Both" else [deal_kind]
        with st.status("Requesting exchange data…",expanded=True) as status:
            for ex in exchanges:
                for kind in kinds:
                    try:
                        st.write(f"Fetching {ex} {kind.lower()}…")
                        x=fetch_csv(ex,from_date,to_date,kind)
                        if not x.empty: frames.append(x)
                    except Exception as e: errors.append(f"{ex} {kind}: {e}")
            status.update(label="Fetch attempt complete",state="complete",expanded=False)
for e in errors: st.warning(e)

if frames:
    raw=pd.concat(frames,ignore_index=True,sort=False)
    d=normalize(raw)
    if d.empty:
        st.error("Could not recognize required CSV columns. Try the official exchange CSV with Date, Symbol/Scrip, Client Name, Buy/Sell, Quantity and Price.")
        st.dataframe(raw,use_container_width=True)
        st.stop()
    d=d[(d.date.dt.date>=from_date)&(d.date.dt.date<=to_date)]
    if deal_kind!="Both":
        d=d[(d.deal_type.str.lower().str.contains(deal_kind.split()[0].lower(),na=False))|(d.deal_type=="unknown")]
    if d.empty: st.info("No matching deal records in selected date range.");st.stop()

    buy=d[d.side=="BUY"];sell=d[d.side=="SELL"]
    m1,m2=st.columns(2);m1.metric("Deal records",f"{len(d):,}");m2.metric("Both-side flags",f"{len(d.groupby(['date','symbol','client_key']).filter(lambda x:set(x.side)=={'BUY','SELL'})):,}")
    m3,m4=st.columns(2);m3.metric("Reported buy value",f"₹{buy.value_cr.sum():,.2f} Cr");m4.metric("Reported sell value",f"₹{sell.value_cr.sum():,.2f} Cr")
    rows=[]
    for symbol,g in d.groupby("symbol"):
        b=g[g.side=="BUY"];s=g[g.side=="SELL"]
        rows.append({"Stock":symbol,"Buy qty":int(b.qty.sum()),"Sell qty":int(s.qty.sum()),"Net qty":int(b.qty.sum()-s.qty.sum()),"Buy value ₹Cr":round(b.value_cr.sum(),2),"Sell value ₹Cr":round(s.value_cr.sum(),2),"Net value ₹Cr":round(b.value_cr.sum()-s.value_cr.sum(),2),"Buyers":b.client_key.nunique(),"Sellers":s.client_key.nunique(),"Signal":"Net disclosed buying" if b.qty.sum()>s.qty.sum() else ("Net disclosed selling" if b.qty.sum()<s.qty.sum() else "Balanced")})
    stocks=pd.DataFrame(rows).sort_values("Net value ₹Cr",ascending=False)
    client_rows=[]
    for (key,name),g in d.groupby(["client_key","client"]):
        b=g[g.side=="BUY"];s=g[g.side=="SELL"]
        client_rows.append({"Client":name,"Stocks":", ".join(sorted(g.symbol.unique())[:10]),"Buy qty":int(b.qty.sum()),"Sell qty":int(s.qty.sum()),"Net qty":int(b.qty.sum()-s.qty.sum()),"Buy value ₹Cr":round(b.value_cr.sum(),2),"Sell value ₹Cr":round(s.value_cr.sum(),2),"Net value ₹Cr":round(b.value_cr.sum()-s.value_cr.sum(),2),"Buy dates":b.date.dt.date.nunique(),"Both sides":bool(not b.empty and not s.empty)})
    clients=pd.DataFrame(client_rows).sort_values(["Buy dates","Net value ₹Cr"],ascending=False)
    flags=[]
    for (dt,sym,key),g in d.groupby(["date","symbol","client_key"]):
        b=g[g.side=="BUY"].qty.sum();s=g[g.side=="SELL"].qty.sum()
        if b>0 and s>0: flags.append({"Date":dt.date(),"Stock":sym,"Client":g.client.iloc[0],"Buy qty":int(b),"Sell qty":int(s),"Net qty":int(b-s),"Note":"Both sides disclosed; not proof of same shares"})
    both=pd.DataFrame(flags)
    t1,t2,t3,t4=st.tabs(["Stocks","Clients","Both sides","All deals"])
    with t1:
        st.dataframe(stocks,use_container_width=True,hide_index=True)
        st.download_button("Download stock summary CSV",stocks.to_csv(index=False).encode(),"stock_summary.csv","text/csv",use_container_width=True)
    with t2:
        min_days=st.selectbox("Repeat buyer: minimum distinct buy dates",[2,3,4,5,7],index=0)
        st.dataframe(clients[clients["Buy dates"]>=min_days],use_container_width=True,hide_index=True)
        st.download_button("Download client activity CSV",clients.to_csv(index=False).encode(),"client_activity.csv","text/csv",use_container_width=True)
    with t3:
        st.dataframe(both,use_container_width=True,hide_index=True)
        st.download_button("Download both-side flags CSV",both.to_csv(index=False).encode(),"both_side_flags.csv","text/csv",use_container_width=True)
    with t4:
        st.dataframe(d.sort_values(["date","symbol"],ascending=[False,True]),use_container_width=True,hide_index=True)
        st.download_button("Download normalized deals CSV",d.to_csv(index=False).encode(),"all_deals.csv","text/csv",use_container_width=True)
else:
    st.markdown("### What it finds")
    st.markdown("- Net disclosed buying/selling by stock\n- Repeat disclosed buyers across dates\n- Same client appearing on both sides for a stock/date\n- CSV exports for each analysis")
    st.info("For reliable access on your phone, deploy this app online or run it on a computer connected to the same Wi-Fi. Live exchange endpoints may block automated requests; CSV upload is the fallback.")

st.divider()
st.caption("Research only, not financial advice. Data includes only fetched/uploaded disclosures and may not represent a firm's complete position.")
