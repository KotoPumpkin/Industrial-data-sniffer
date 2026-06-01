import requests
url = 'http://localhost:8086/api/v2/query'
params = {'org': 'industrial'}
headers = {
    'Authorization': 'Token my-super-secret-admin-token-2024',
    'Content-Type': 'application/vnd.flux',
    'Accept': 'application/csv'
}
flux = '''from(bucket: "factory") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "industrial_metrics") |> limit(n: 5)'''
r = requests.post(url, params=params, headers=headers, data=flux)
print(f"Status: {r.status_code}")
