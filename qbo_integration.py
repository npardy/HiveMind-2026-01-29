"""
QuickBooks Online Integration
Handles OAuth, project creation, invoice generation, customer management
"""

import logging
from typing import Dict, Optional
import requests
import json
import os
from datetime import datetime
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import base64

logger = logging.getLogger(__name__)

class QBOOAuthHandler(BaseHTTPRequestHandler):
    """Handles OAuth2 callback from QuickBooks"""
    auth_code = None
    realm_id = None
    
    def do_GET(self):
        """Handle GET request with auth code"""
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'code' in params:
            QBOOAuthHandler.auth_code = params['code'][0]
            QBOOAuthHandler.realm_id = params.get('realmId', [None])[0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html><body>
                <h1>QuickBooks Authorization Successful!</h1>
                <p>You can close this window and return to the application.</p>
                <script>window.close();</script>
                </body></html>
            """)
        else:
            error = params.get('error', ['Unknown'])[0]
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Authorization Failed</h1><p>{error}</p></body></html>".encode())
    
    def log_message(self, format, *args):
        """Suppress logging"""
        pass


class QBOIntegration:
    """QuickBooks Online API integration"""

    def __init__(self, client_id: str, client_secret: str,
                 redirect_uri: str, environment: str = "production",
                 token_cache_file: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.environment = environment
        self.access_token = None
        self.refresh_token = None
        self.realm_id = None
        self.logger = logging.getLogger(__name__)

        # Token cache path - use provided value, or try config_loader, or fallback
        if token_cache_file:
            self.TOKEN_CACHE_FILE = token_cache_file
        else:
            try:
                from config_loader import get_config
                self.TOKEN_CACHE_FILE = get_config().token_cache_qbo
            except Exception:
                # Fallback for standalone use
                self.TOKEN_CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "qbo_token_cache.json")
        
        # API endpoints - token endpoint is always the same
        self.token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        
        if environment == "production":
            self.base_url = "https://quickbooks.api.intuit.com"
        else:
            self.base_url = "https://sandbox-quickbooks.api.intuit.com"
        
        self.auth_url = "https://appcenter.intuit.com/connect/oauth2"
        
        # Try to load cached tokens
        self._load_token_cache()

    def _load_token_cache(self):
        """Load tokens from cache file"""
        if os.path.exists(self.TOKEN_CACHE_FILE):
            try:
                with open(self.TOKEN_CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                    self.access_token = cache.get('access_token')
                    self.refresh_token = cache.get('refresh_token')
                    self.realm_id = cache.get('realm_id')
                    self.logger.info(f"Loaded QBO tokens from cache (realm: {self.realm_id})")
            except Exception as e:
                self.logger.warning(f"Could not load token cache: {e}")
    
    def _save_token_cache(self):
        """Save tokens to cache file"""
        try:
            cache = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'realm_id': self.realm_id
            }
            with open(self.TOKEN_CACHE_FILE, 'w') as f:
                json.dump(cache, f)
            self.logger.info("Saved QBO tokens to cache")
        except Exception as e:
            self.logger.error(f"Could not save token cache: {e}")
    
    def authenticate(self) -> bool:
        """Authenticate with QuickBooks - try cache first, then interactive"""
        # If we have tokens, try to use/refresh them
        if self.access_token and self.refresh_token and self.realm_id:
            self.logger.info("Found cached QBO tokens, testing...")
            if self._test_connection():
                return True
            # Try refresh
            self.logger.info("Cached token expired, attempting refresh...")
            if self._refresh_tokens():
                return True
        
        # Need interactive auth
        self.logger.info("Starting interactive QBO authentication...")
        return self._interactive_auth()
    
    def _interactive_auth(self) -> bool:
        """Start OAuth flow with browser"""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'com.intuit.quickbooks.accounting',
            'state': 'security_token'
        }
        
        auth_url = f"{self.auth_url}?{urllib.parse.urlencode(params)}"
        
        self.logger.info("Opening browser for QuickBooks authorization...")
        print(f"\nIf browser doesn't open, go to:\n{auth_url}\n")
        
        # Reset handler state
        QBOOAuthHandler.auth_code = None
        QBOOAuthHandler.realm_id = None
        
        # Start callback server
        server = HTTPServer(('localhost', 8000), QBOOAuthHandler)
        server.timeout = 300  # 5 minute timeout
        
        # Open browser
        webbrowser.open(auth_url)
        
        print("Waiting for QuickBooks authorization (5 min timeout)...")
        server.handle_request()
        server.server_close()
        
        if not QBOOAuthHandler.auth_code:
            self.logger.error("Failed to get authorization code")
            return False
        
        # Exchange code for tokens
        return self._exchange_code(QBOOAuthHandler.auth_code, QBOOAuthHandler.realm_id)

    def _exchange_code(self, auth_code: str, realm_id: str) -> bool:
        """Exchange authorization code for tokens"""
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.redirect_uri
        }
        
        try:
            response = requests.post(self.token_url, data=data, headers=headers)
            response.raise_for_status()
            
            tokens = response.json()
            self.access_token = tokens['access_token']
            self.refresh_token = tokens['refresh_token']
            self.realm_id = realm_id
            
            self._save_token_cache()
            self.logger.info(f"QBO authentication successful! Realm ID: {realm_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exchanging code for tokens: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response: {e.response.text}")
            return False
    
    def _refresh_tokens(self) -> bool:
        """Refresh access token using refresh token"""
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        
        try:
            response = requests.post(self.token_url, data=data, headers=headers)
            response.raise_for_status()
            
            tokens = response.json()
            self.access_token = tokens['access_token']
            self.refresh_token = tokens.get('refresh_token', self.refresh_token)
            
            self._save_token_cache()
            self.logger.info("QBO token refresh successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            return False
    
    def _test_connection(self) -> bool:
        """Test if current tokens work"""
        try:
            result = self._make_request('GET', '/companyinfo/' + self.realm_id)
            return result is not None
        except:
            return False

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make authenticated request to QBO API"""
        if not self.access_token or not self.realm_id:
            self.logger.error("Not authenticated. Call authenticate() first.")
            return None
        
        url = f"{self.base_url}/v3/company/{self.realm_id}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Handle token expiry
            if response.status_code == 401:
                self.logger.info("Token expired, refreshing...")
                if self._refresh_tokens():
                    return self._make_request(method, endpoint, data)
                return None
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except Exception as e:
            self.logger.error(f"API request failed: {e}")
            return None
    
    def find_or_create_customer(self, name: str, email: str = None) -> Optional[str]:
        """
        Find existing customer or create new one, returns customer ID.

        Search order (to avoid creating duplicates):
        1. By email address (most reliable for returning clients)
        2. By exact DisplayName match
        3. By partial name match (LIKE)
        4. By email domain (for law firms, etc.)
        5. Only create if not found by any method
        """
        # 1. Search by email first (most reliable)
        if email:
            query = f"SELECT * FROM Customer WHERE PrimaryEmailAddr = '{email}'"
            result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

            if result and result.get('QueryResponse', {}).get('Customer'):
                customer = result['QueryResponse']['Customer'][0]
                customer_id = customer['Id']
                self.logger.info(f"Found existing customer by email: {customer.get('DisplayName')} (ID: {customer_id})")
                return customer_id

        # 2. Search by exact DisplayName match
        query = f"SELECT * FROM Customer WHERE DisplayName = '{name}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('Customer'):
            customer_id = result['QueryResponse']['Customer'][0]['Id']
            self.logger.info(f"Found existing customer by exact name: {name} (ID: {customer_id})")
            return customer_id

        # 3. Search by partial name match (LIKE)
        # This catches cases like "Van Driel Law" vs "Van Driel Law Corp"
        query = f"SELECT * FROM Customer WHERE DisplayName LIKE '%{name}%'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('Customer'):
            customer = result['QueryResponse']['Customer'][0]
            customer_id = customer['Id']
            self.logger.info(f"Found existing customer by partial name match: {customer.get('DisplayName')} (ID: {customer_id})")
            return customer_id

        # 4. Search by email domain for business clients (law firms, etc.)
        if email and '@' in email:
            domain = email.split('@')[1]
            # Only do domain search for business domains (not gmail, outlook, etc.)
            common_personal_domains = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'icloud.com', 'live.com']
            if domain.lower() not in common_personal_domains:
                # Get recent customers and check email domain
                query = "SELECT * FROM Customer ORDER BY MetaData.CreateTime DESC MAXRESULTS 200"
                result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

                if result and result.get('QueryResponse', {}).get('Customer'):
                    for customer in result['QueryResponse']['Customer']:
                        cust_email = customer.get('PrimaryEmailAddr', {}).get('Address', '')
                        if cust_email and domain.lower() in cust_email.lower():
                            customer_id = customer['Id']
                            self.logger.info(f"Found existing customer by email domain ({domain}): {customer.get('DisplayName')} (ID: {customer_id})")
                            return customer_id

        # 5. Create new customer only if not found by any method
        customer_data = {
            'DisplayName': name
        }
        if email:
            customer_data['PrimaryEmailAddr'] = {'Address': email}

        result = self._make_request('POST', '/customer', customer_data)

        if result and result.get('Customer'):
            customer_id = result['Customer']['Id']
            self.logger.info(f"Created new customer: {name} (ID: {customer_id})")
            return customer_id

        return None
    
    def find_customer_by_email(self, email: str) -> Optional[Dict]:
        """Find customer by email address, returns full customer object"""
        query = f"SELECT * FROM Customer WHERE PrimaryEmailAddr = '{email}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Customer'):
            return result['QueryResponse']['Customer'][0]
        return None
    
    def find_customer_by_name(self, name: str) -> Optional[Dict]:
        """Find customer by display name, returns full customer object"""
        query = f"SELECT * FROM Customer WHERE DisplayName LIKE '%{name}%'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Customer'):
            return result['QueryResponse']['Customer'][0]
        return None
    
    def create_project(self, customer_id: str, project_name: str, 
                      description: str = "") -> Optional[str]:
        """Create a project (sub-customer) for customer"""
        project_data = {
            'ParentRef': {'value': customer_id},
            'DisplayName': project_name,
            'Job': True
        }
        if description:
            project_data['Notes'] = description
        
        result = self._make_request('POST', '/customer', project_data)
        
        if result and result.get('Customer'):
            project_id = result['Customer']['Id']
            self.logger.info(f"Created project: {project_name} (ID: {project_id})")
            return project_id
        
        return None

    def create_invoice(self, customer_id: str, line_items: list,
                      project_id: str = None, due_date: str = None) -> Optional[Dict]:
        """
        Create an invoice
        
        line_items format: [
            {'description': 'Survey work', 'amount': 500.00, 'quantity': 1},
            ...
        ]
        """
        invoice_data = {
            'CustomerRef': {'value': project_id if project_id else customer_id},
            'Line': []
        }
        
        for item in line_items:
            invoice_data['Line'].append({
                'DetailType': 'SalesItemLineDetail',
                'Amount': item['amount'] * item.get('quantity', 1),
                'SalesItemLineDetail': {
                    'Qty': item.get('quantity', 1),
                    'UnitPrice': item['amount']
                },
                'Description': item['description']
            })
        
        if due_date:
            invoice_data['DueDate'] = due_date
        
        result = self._make_request('POST', '/invoice', invoice_data)
        
        if result and result.get('Invoice'):
            invoice_id = result['Invoice']['Id']
            invoice_num = result['Invoice'].get('DocNumber', 'N/A')
            self.logger.info(f"Created invoice #{invoice_num} (ID: {invoice_id})")
            return result['Invoice']
        
        return None
    
    def get_invoice_pdf(self, invoice_id: str) -> Optional[bytes]:
        """Get invoice PDF"""
        url = f"{self.base_url}/v3/company/{self.realm_id}/invoice/{invoice_id}/pdf"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/pdf'
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            self.logger.error(f"Error getting invoice PDF: {e}")
            return None
    
    def create_estimate(self, customer_id: str, line_items: list,
                        doc_number: str = None, expiration_date: str = None,
                        customer_memo: str = None) -> Optional[Dict]:
        """
        Create an estimate/quote in QBO.

        Args:
            customer_id: QBO customer ID
            line_items: List of dicts with 'amount', 'description', and optional 'quantity'
            doc_number: Custom estimate number (e.g., "E26-005 - St. John's")
            expiration_date: Quote expiration date (YYYY-MM-DD)
            customer_memo: Note visible to customer

        Returns:
            QBO Estimate object or None
        """
        estimate_data = {
            'CustomerRef': {'value': customer_id},
            'Line': []
        }

        if doc_number:
            estimate_data['DocNumber'] = doc_number
        if expiration_date:
            estimate_data['ExpirationDate'] = expiration_date
        if customer_memo:
            estimate_data['CustomerMemo'] = {'value': customer_memo}

        for item in line_items:
            line = {
                'DetailType': 'SalesItemLineDetail',
                'Amount': item['amount'] * item.get('quantity', 1),
                'Description': item.get('description', '')
            }
            # Add item reference if provided
            if item.get('item_id'):
                line['SalesItemLineDetail'] = {
                    'ItemRef': {'value': item['item_id']},
                    'Qty': item.get('quantity', 1),
                    'UnitPrice': item['amount']
                }
            estimate_data['Line'].append(line)

        result = self._make_request('POST', '/estimate', estimate_data)

        if result and result.get('Estimate'):
            self.logger.info(f"Created estimate ID: {result['Estimate']['Id']}, DocNumber: {result['Estimate'].get('DocNumber')}")
            return result['Estimate']

        return None

    def get_estimate(self, estimate_id: str) -> Optional[Dict]:
        """Get an estimate by ID."""
        result = self._make_request('GET', f'/estimate/{estimate_id}')
        if result and result.get('Estimate'):
            return result['Estimate']
        return None

    def search_estimates(self, customer_id: str = None, doc_number: str = None,
                         status: str = None, recent_count: int = 20) -> list:
        """
        Search for estimates.

        Args:
            customer_id: Filter by customer
            doc_number: Filter by estimate number (partial match)
            status: Filter by status (Pending, Accepted, Closed, Rejected)
            recent_count: How many to return if no filters

        Returns:
            List of estimate objects
        """
        conditions = []

        if customer_id:
            conditions.append(f"CustomerRef = '{customer_id}'")
        if status:
            conditions.append(f"TxnStatus = '{status}'")

        if conditions:
            where_clause = " AND ".join(conditions)
            query = f"SELECT * FROM Estimate WHERE {where_clause} ORDERBY TxnDate DESC MAXRESULTS {recent_count}"
        else:
            query = f"SELECT * FROM Estimate ORDERBY TxnDate DESC MAXRESULTS {recent_count}"

        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        estimates = result.get('QueryResponse', {}).get('Estimate', []) if result else []

        # If searching by doc_number, filter client-side (QBO doesn't support LIKE on DocNumber)
        if doc_number and estimates:
            doc_lower = doc_number.lower()
            estimates = [e for e in estimates if doc_lower in e.get('DocNumber', '').lower()]

        self.logger.info(f"Found {len(estimates)} estimates")
        return estimates

    def send_estimate(self, estimate_id: str, recipient_email: str = None) -> bool:
        """
        Send an estimate via QBO email.

        Args:
            estimate_id: QBO estimate ID
            recipient_email: Override recipient (uses customer email if not provided)

        Returns:
            True if sent successfully
        """
        endpoint = f'/estimate/{estimate_id}/send'
        if recipient_email:
            endpoint += f'?sendTo={recipient_email}'

        result = self._make_request('POST', endpoint, {})

        if result and result.get('Estimate'):
            self.logger.info(f"Sent estimate {estimate_id} to {recipient_email or 'customer email'}")
            return True
        return False

    def update_estimate_status(self, estimate_id: str, status: str) -> Optional[Dict]:
        """
        Update estimate status.

        Args:
            estimate_id: QBO estimate ID
            status: New status (Pending, Accepted, Closed, Rejected)

        Returns:
            Updated estimate or None
        """
        # First get the current estimate (need SyncToken)
        current = self.get_estimate(estimate_id)
        if not current:
            return None

        update_data = {
            'Id': estimate_id,
            'SyncToken': current['SyncToken'],
            'TxnStatus': status
        }

        result = self._make_request('POST', '/estimate', update_data)

        if result and result.get('Estimate'):
            self.logger.info(f"Updated estimate {estimate_id} status to {status}")
            return result['Estimate']
        return None

    def convert_estimate_to_invoice(self, estimate_id: str) -> Optional[Dict]:
        """
        Convert an accepted estimate to an invoice.

        Args:
            estimate_id: QBO estimate ID

        Returns:
            New invoice object or None
        """
        # Get the estimate details
        estimate = self.get_estimate(estimate_id)
        if not estimate:
            self.logger.error(f"Estimate {estimate_id} not found")
            return None

        # Build invoice from estimate data
        invoice_data = {
            'CustomerRef': estimate['CustomerRef'],
            'Line': estimate.get('Line', []),
            'LinkedTxn': [{
                'TxnId': estimate_id,
                'TxnType': 'Estimate'
            }]
        }

        # Copy optional fields
        if estimate.get('CustomerMemo'):
            invoice_data['CustomerMemo'] = estimate['CustomerMemo']
        if estimate.get('BillEmail'):
            invoice_data['BillEmail'] = estimate['BillEmail']

        result = self._make_request('POST', '/invoice', invoice_data)

        if result and result.get('Invoice'):
            self.logger.info(f"Converted estimate {estimate_id} to invoice {result['Invoice']['Id']}")
            return result['Invoice']

        return None

    def get_next_estimate_number(self, community: str = None) -> str:
        """
        Get next estimate number with optional community suffix.

        Format: "E26-005" or "E26-005 - St. John's" (abbreviated if needed)

        Args:
            community: Optional community name to append

        Returns:
            Next estimate number string
        """
        year_prefix = f"E{datetime.now().strftime('%y')}-"

        # Get recent estimates to find highest number
        estimates = self.search_estimates(recent_count=50)

        highest = 0
        for est in estimates:
            doc_num = est.get('DocNumber', '')
            if doc_num.startswith(year_prefix):
                try:
                    # Extract number part (E26-005 -> 005)
                    num_part = doc_num[len(year_prefix):].split()[0].split('-')[0]
                    num = int(num_part)
                    highest = max(highest, num)
                except (ValueError, IndexError):
                    pass

        next_num = f"{year_prefix}{highest + 1:03d}"

        # Add community suffix if provided (QBO has character limit ~21 chars)
        if community:
            # Abbreviate long community names
            abbrevs = {
                "St. John's": "St. J",
                "Mount Pearl": "Mt. Pearl",
                "Paradise": "Paradise",
                "Conception Bay South": "CBS",
                "Portugal Cove-St. Philip's": "PCSP",
                "Logy Bay-Middle Cove-Outer Cove": "Logy Bay",
                "Holyrood": "Holyrood",
                "Petty Harbour-Maddox Cove": "Petty Hr",
            }
            short_community = abbrevs.get(community, community[:10])
            next_num = f"{next_num} - {short_community}"

        return next_num

    def get_company_info(self) -> Optional[Dict]:
        """Get company info - useful for testing connection"""
        result = self._make_request('GET', f'/companyinfo/{self.realm_id}')
        if result and result.get('CompanyInfo'):
            return result['CompanyInfo']
        return None
    
    def get_items(self) -> Optional[list]:
        """Get all products/services (Items) from QBO"""
        query = "SELECT * FROM Item WHERE Type = 'Service'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Item'):
            items = result['QueryResponse']['Item']
            self.logger.info(f"Found {len(items)} service items")
            return items
        return []
    
    def find_item_by_name(self, name: str) -> Optional[Dict]:
        """Find a product/service item by name"""
        query = f"SELECT * FROM Item WHERE Name = '{name}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Item'):
            return result['QueryResponse']['Item'][0]
        return None
    
    def create_job(self, customer_name: str, customer_email: str, 
                   property_address: str, community: str,
                   item_name: str = "Boundary Survey & Real Property Report",
                   amount: float = None, due_date: str = None) -> Optional[Dict]:
        """
        Create a complete job: Customer + Project + Invoice
        Returns dict with job_number, customer_id, project_id, invoice_id
        
        Description format: "ADDRESS, COMMUNITY, NL" (for geocoding)
        """
        # 1. Get next job number
        job_number = self.get_next_job_number()
        
        # 2. Format description with province for geocoding
        job_description = f"{property_address}, {community}, NL"
        
        # 3. Find or create customer
        customer_id = self.find_or_create_customer(customer_name, customer_email)
        if not customer_id:
            self.logger.error("Failed to create/find customer")
            return None
        
        # 4. Create project under customer (with due date in notes)
        project_notes = job_description
        if due_date:
            project_notes += f"\nDue: {due_date}"
        
        project_id = self.create_project(customer_id, job_number, 
                                         description=project_notes)
        if not project_id:
            self.logger.error("Failed to create project")
            return None
        
        # 5. Create invoice with due date
        if amount is None:
            # Look up item price
            item = self.find_item_by_name(item_name)
            if item and item.get('UnitPrice'):
                amount = float(item['UnitPrice'])
            else:
                self.logger.warning(f"Could not find price for {item_name}, using 0")
                amount = 0
        
        invoice = self.create_invoice_with_item(
            customer_id=customer_id,
            item_name=item_name,
            amount=amount,
            project_id=project_id,
            due_date=due_date,
            description=job_description  # "15 Forest Road, St. John's, NL"
        )
        
        # 6. Set invoice DocNumber to match job number
        if invoice:
            # Update invoice DocNumber
            update_data = {
                'Id': invoice['Id'],
                'SyncToken': invoice['SyncToken'],
                'DocNumber': job_number,
                'sparse': True
            }
            updated = self._make_request('POST', '/invoice', update_data)
            if updated:
                invoice = updated.get('Invoice', invoice)
        
        return {
            'job_number': job_number,
            'customer_id': customer_id,
            'project_id': project_id,
            'invoice_id': invoice['Id'] if invoice else None,
            'invoice_number': invoice.get('DocNumber') if invoice else None
        }
    
    def find_invoice_by_project(self, project_id: str) -> Optional[Dict]:
        """Find invoice(s) for a specific project/job"""
        query = f"SELECT * FROM Invoice WHERE CustomerRef = '{project_id}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Invoice'):
            invoices = result['QueryResponse']['Invoice']
            self.logger.info(f"Found {len(invoices)} invoice(s) for project {project_id}")
            return invoices[0] if invoices else None  # Return most recent
        return None
    
    def get_invoice_by_id(self, invoice_id: str) -> Optional[Dict]:
        """Get a specific invoice by ID"""
        result = self._make_request('GET', f"/invoice/{invoice_id}")
        if result and result.get('Invoice'):
            return result['Invoice']
        return None
    
    def find_invoice_by_number(self, doc_number: str) -> Optional[Dict]:
        """Find invoice by document number (e.g., '26-005')"""
        query = f"SELECT * FROM Invoice WHERE DocNumber = '{doc_number}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Invoice'):
            return result['QueryResponse']['Invoice'][0]
        return None
    
    def find_project_by_name(self, project_name: str) -> Optional[Dict]:
        """Find a project by name (for looking up by address)"""
        # Projects are sub-customers with Job=true
        query = f"SELECT * FROM Customer WHERE DisplayName LIKE '%{project_name}%' AND Job = true"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Customer'):
            projects = result['QueryResponse']['Customer']
            self.logger.info(f"Found {len(projects)} matching project(s)")
            return projects[0] if projects else None
        return None
    
    def send_invoice(self, invoice_id: str, email_address: str = None) -> bool:
        """
        Send invoice via QBO email.
        If email_address not provided, uses customer's email on file.
        
        NOTE: The /send endpoint requires NO Content-Type header or octet-stream.
        Using application/json causes a 500 NullPointerException on QBO's side.
        """
        if not self.access_token or not self.realm_id:
            self.logger.error("Not authenticated")
            return False
        
        url = f"{self.base_url}/v3/company/{self.realm_id}/invoice/{invoice_id}/send"
        if email_address:
            url += f"?sendTo={urllib.parse.quote(email_address)}"
        
        # CRITICAL: Do NOT include Content-Type: application/json
        # The send endpoint breaks with that header
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(url, headers=headers)
            
            if response.status_code == 401:
                self.logger.info("Token expired, refreshing...")
                if self._refresh_tokens():
                    return self.send_invoice(invoice_id, email_address)
                return False
            
            if response.status_code == 200:
                self.logger.info(f"Invoice {invoice_id} sent successfully")
                return True
            else:
                self.logger.error(f"Failed to send invoice: {response.status_code} - {response.text[:200]}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending invoice: {e}")
            return False
    
    def create_invoice_with_item(self, customer_id: str, item_name: str,
                                  amount: float, project_id: str = None,
                                  due_date: str = None, description: str = None) -> Optional[Dict]:
        """
        Create invoice using a named product/service item.
        This links to your existing QBO items for proper reporting.
        """
        # Find the item
        item = self.find_item_by_name(item_name)
        if not item:
            self.logger.warning(f"Item '{item_name}' not found, using generic line")
            return self.create_invoice(customer_id, 
                [{'description': item_name, 'amount': amount, 'quantity': 1}],
                project_id, due_date)
        
        invoice_data = {
            'CustomerRef': {'value': project_id if project_id else customer_id},
            'Line': [{
                'DetailType': 'SalesItemLineDetail',
                'Amount': amount,
                'SalesItemLineDetail': {
                    'ItemRef': {'value': item['Id'], 'name': item['Name']},
                    'Qty': 1,
                    'UnitPrice': amount
                },
                'Description': description or item.get('Description', '')
            }]
        }
        
        if due_date:
            invoice_data['DueDate'] = due_date
        
        result = self._make_request('POST', '/invoice', invoice_data)
        
        if result and result.get('Invoice'):
            invoice = result['Invoice']
            self.logger.info(f"Created invoice #{invoice.get('DocNumber')} with item '{item_name}'")
            return invoice
        
        return None
    
    def get_next_job_number(self) -> str:
        """
        Get the next job number by finding the highest invoice number for the current year.
        Job numbers follow format: YY-NNN (e.g., 26-004, 26-005)
        """
        from datetime import datetime
        
        year_prefix = datetime.now().strftime('%y')  # "26" for 2026
        
        # Query invoices starting with this year's prefix, sorted descending
        query = f"SELECT DocNumber FROM Invoice WHERE DocNumber LIKE '{year_prefix}-%' ORDER BY DocNumber DESC MAXRESULTS 1"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Invoice'):
            last_invoice = result['QueryResponse']['Invoice'][0]
            last_num = last_invoice.get('DocNumber', f'{year_prefix}-000')
            
            # Parse and increment: "26-004" -> 4 -> 5 -> "26-005"
            try:
                num_part = int(last_num.split('-')[1])
                next_num = num_part + 1
                return f"{year_prefix}-{next_num:03d}"
            except (IndexError, ValueError):
                self.logger.warning(f"Could not parse invoice number: {last_num}")
                return f"{year_prefix}-001"
        else:
            # No invoices for this year yet
            return f"{year_prefix}-001"
    
    def create_job_invoice(self, customer_id: str, job_number: str, 
                           item_name: str = "Boundary Survey & Real Property Report",
                           amount: float = None, project_id: str = None,
                           due_date: str = None, property_address: str = None) -> Optional[Dict]:
        """
        Create an invoice with a specific job number (DocNumber).
        This is the main method for creating invoices from job requests.
        
        NOTE: project_id should be the sub-customer (job) ID, NOT a ProjectRef.
        In QBO, invoices use CustomerRef pointing to the sub-customer.
        """
        # Find the item
        item = self.find_item_by_name(item_name)
        if not item:
            self.logger.error(f"Item '{item_name}' not found in QBO")
            return None
        
        # Use item's default price if not specified
        if amount is None:
            amount = float(item.get('UnitPrice', 0))
        
        description = property_address or item.get('Description', '')
        
        # Get tax code from item or use default HST NL (value: 7)
        tax_code = item.get('SalesTaxCodeRef', {}).get('value', '7')
        
        invoice_data = {
            'DocNumber': job_number,  # Our job number!
            'CustomerRef': {'value': project_id if project_id else customer_id},
            'Line': [{
                'DetailType': 'SalesItemLineDetail',
                'Amount': amount,
                'SalesItemLineDetail': {
                    'ItemRef': {'value': item['Id'], 'name': item['Name']},
                    'Qty': 1,
                    'UnitPrice': amount,
                    'TaxCodeRef': {'value': tax_code}  # Required for Canadian HST
                },
                'Description': description
            }]
        }
        
        if due_date:
            invoice_data['DueDate'] = due_date
        
        result = self._make_request('POST', '/invoice', invoice_data)
        
        if result and result.get('Invoice'):
            invoice = result['Invoice']
            self.logger.info(f"Created job invoice #{job_number} for ${amount}")
            return invoice
        
        return None
    
    def get_recent_invoices(self, limit: int = 30) -> list:
        """Get recent invoices with their descriptions (addresses)."""
        query = f"SELECT * FROM Invoice ORDER BY MetaData.CreateTime DESC MAXRESULTS {limit}"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        if result and result.get('QueryResponse', {}).get('Invoice'):
            return result['QueryResponse']['Invoice']
        return []
    
    def find_invoices_by_customer_email(self, email: str) -> list:
        """Find all invoices for a customer by their email address."""
        # First find customer by email
        query = f"SELECT * FROM Customer WHERE PrimaryEmailAddr = '{email}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        customers = result.get('QueryResponse', {}).get('Customer', []) if result else []
        
        if not customers:
            return []
        
        # Get invoices for this customer
        all_invoices = []
        for customer in customers:
            cust_id = customer['Id']
            inv_query = f"SELECT * FROM Invoice WHERE CustomerRef = '{cust_id}' ORDER BY MetaData.CreateTime DESC MAXRESULTS 20"
            inv_result = self._make_request('GET', f"/query?query={urllib.parse.quote(inv_query)}")
            
            if inv_result and inv_result.get('QueryResponse', {}).get('Invoice'):
                all_invoices.extend(inv_result['QueryResponse']['Invoice'])
        
        return all_invoices
    
    def find_invoices_by_company_domain(self, email_domain: str) -> list:
        """Find invoices for any customer with email from the same domain."""
        # QBO doesn't support LIKE queries on email, so get recent customers and filter
        query = "SELECT * FROM Customer ORDER BY MetaData.CreateTime DESC MAXRESULTS 200"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")
        
        customers = result.get('QueryResponse', {}).get('Customer', []) if result else []
        
        # Filter to matching domain
        matching_customers = []
        for c in customers:
            cust_email = c.get('PrimaryEmailAddr', {}).get('Address', '')
            if cust_email and email_domain.lower() in cust_email.lower():
                matching_customers.append(c)
        
        if not matching_customers:
            return []
        
        # Get invoices for matching customers
        all_invoices = []
        for customer in matching_customers[:10]:  # Limit to avoid too many calls
            cust_id = customer['Id']
            inv_query = f"SELECT * FROM Invoice WHERE CustomerRef = '{cust_id}' ORDER BY MetaData.CreateTime DESC MAXRESULTS 10"
            inv_result = self._make_request('GET', f"/query?query={urllib.parse.quote(inv_query)}")
            
            if inv_result and inv_result.get('QueryResponse', {}).get('Invoice'):
                all_invoices.extend(inv_result['QueryResponse']['Invoice'])
        
        return all_invoices
    
    def search_invoice_by_address(self, address: str, invoices: list = None) -> Optional[Dict]:
        """
        Search for an invoice matching an address in its description.
        If invoices not provided, searches recent invoices.
        """
        if invoices is None:
            invoices = self.get_recent_invoices(30)
        
        address_lower = address.lower().strip()
        
        # Try exact match first, then partial
        for inv in invoices:
            for line in inv.get('Line', []):
                desc = line.get('Description', '').lower()
                if address_lower in desc:
                    self.logger.info(f"Found invoice by address match: #{inv.get('DocNumber')}")
                    return inv
        
        # Try matching just street number and name (without community)
        # e.g., "15 Forest Road" should match "15 Forest Road, St. John's, NL"
        address_parts = address_lower.split(',')[0].strip()  # Get just "15 Forest Road"
        if address_parts != address_lower:
            for inv in invoices:
                for line in inv.get('Line', []):
                    desc = line.get('Description', '').lower()
                    if address_parts in desc:
                        self.logger.info(f"Found invoice by partial address match: #{inv.get('DocNumber')}")
                        return inv
        
        return None
    
    def record_payment(self, invoice_id: str, amount: float = None, 
                       payment_date: str = None) -> Optional[Dict]:
        """
        Record a payment against an invoice.
        
        Args:
            invoice_id: QBO Invoice ID
            amount: Payment amount (defaults to invoice balance if not specified)
            payment_date: Date of payment YYYY-MM-DD (defaults to today)
        
        Returns:
            Payment object or None if failed
        """
        # Get the invoice first
        invoice = self.get_invoice_by_id(invoice_id)
        if not invoice:
            self.logger.error(f"Invoice {invoice_id} not found")
            return None
        
        customer_id = invoice.get('CustomerRef', {}).get('value')
        if not customer_id:
            self.logger.error(f"Invoice {invoice_id} has no customer reference")
            return None
        
        # Use invoice balance if amount not specified
        if amount is None:
            amount = float(invoice.get('Balance', 0))
        
        if amount <= 0:
            self.logger.warning(f"Invoice {invoice_id} already has zero balance")
            return {"already_paid": True, "invoice_id": invoice_id}
        
        # Build payment data
        payment_data = {
            'CustomerRef': {'value': customer_id},
            'TotalAmt': amount,
            'Line': [{
                'Amount': amount,
                'LinkedTxn': [{
                    'TxnId': invoice_id,
                    'TxnType': 'Invoice'
                }]
            }]
        }
        
        if payment_date:
            payment_data['TxnDate'] = payment_date
        
        result = self._make_request('POST', '/payment', payment_data)
        
        if result and result.get('Payment'):
            payment = result['Payment']
            self.logger.info(f"Recorded payment of ${amount} for invoice {invoice_id}")
            return payment
        
        return None
    
    def record_payment_by_invoice_number(self, invoice_number: str, amount: float = None,
                                          payment_date: str = None) -> Optional[Dict]:
        """
        Record a payment by invoice number (job number like 25-180).

        This is the main method Claude uses when processing deposit emails.
        """
        # Find the invoice by DocNumber
        invoice = self.find_invoice_by_number(invoice_number)
        if not invoice:
            self.logger.error(f"Invoice #{invoice_number} not found")
            return None

        return self.record_payment(
            invoice_id=invoice.get('Id'),
            amount=amount,
            payment_date=payment_date
        )

    # =========================================================================
    # TIME ENTRIES (TimeActivity)
    # =========================================================================

    def get_employees(self) -> list:
        """Get all employees for time tracking."""
        query = "SELECT * FROM Employee"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('Employee'):
            return result['QueryResponse']['Employee']
        return []

    def find_employee_by_name(self, name: str) -> Optional[Dict]:
        """
        Find employee by name with smart matching.

        Matching strategy (in order):
        1. LIKE partial match (e.g., "Allan" matches "Allan Regular")
        2. First name match (e.g., "Joe" matches "Joseph English" via Joseph→Joe)
        3. Nickname mapping for common variations

        This handles field crew entering short names like "Joe" when QBO has "Joseph English".
        """
        if not name:
            return None

        name_clean = name.strip()

        # 1. Try LIKE partial match first (fastest, handles exact substring matches)
        query = f"SELECT * FROM Employee WHERE DisplayName LIKE '%{name_clean}%'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('Employee'):
            return result['QueryResponse']['Employee'][0]

        # 2. No direct match - get all employees and try smart matching
        all_employees = self.get_employees()
        if not all_employees:
            return None

        name_lower = name_clean.lower()

        # Common nickname → formal name mappings
        nickname_map = {
            'joe': ['joseph', 'joey', 'jo'],
            'joey': ['joseph', 'joe'],
            'joseph': ['joe', 'joey'],
            'nick': ['nicholas', 'nic', 'nicky'],
            'nicholas': ['nick', 'nic', 'nicky'],
            'al': ['allan', 'allen', 'alan'],
            'allan': ['al', 'allen', 'alan'],
            'allen': ['al', 'allan', 'alan'],
            'mike': ['michael', 'mick'],
            'michael': ['mike', 'mick'],
            'bob': ['robert', 'rob', 'bobby'],
            'robert': ['bob', 'rob', 'bobby'],
            'bill': ['william', 'will', 'billy'],
            'william': ['bill', 'will', 'billy'],
            'dave': ['david', 'davey'],
            'david': ['dave', 'davey'],
            'dan': ['daniel', 'danny'],
            'daniel': ['dan', 'danny'],
            'tom': ['thomas', 'tommy'],
            'thomas': ['tom', 'tommy'],
            'jim': ['james', 'jimmy'],
            'james': ['jim', 'jimmy'],
            'steve': ['steven', 'stephen'],
            'steven': ['steve', 'stephen'],
            'stephen': ['steve', 'steven'],
        }

        # Get possible variations of the search name
        possible_names = [name_lower]
        if name_lower in nickname_map:
            possible_names.extend(nickname_map[name_lower])

        # Try to match against each employee
        for emp in all_employees:
            display_name = emp.get('DisplayName', '').lower()
            given_name = emp.get('GivenName', '').lower()
            family_name = emp.get('FamilyName', '').lower()

            for possible in possible_names:
                # Check if any variation matches the display name, given name, or starts with it
                if possible in display_name:
                    self.logger.info(f"Found employee by nickname match: '{name}' -> '{emp.get('DisplayName')}'")
                    return emp
                if given_name and (possible == given_name or given_name.startswith(possible)):
                    self.logger.info(f"Found employee by first name match: '{name}' -> '{emp.get('DisplayName')}'")
                    return emp

        self.logger.warning(f"Employee '{name}' not found in QBO (tried {len(possible_names)} variations)")
        return None

    def create_time_entry(self, employee_id: str, hours: float,
                          job_number: str = None, service_item_id: str = None,
                          description: str = None, date: str = None,
                          billable: bool = True) -> Optional[Dict]:
        """
        Create a time entry (TimeActivity) in QBO.

        Args:
            employee_id: QBO Employee ID
            hours: Number of hours (decimal, e.g., 2.5 for 2h 30m)
            job_number: Job number to link to (e.g., "26-001") - will find project
            service_item_id: Service item ID (e.g., "2" for Field Time)
            description: Description of work done
            date: Date of work YYYY-MM-DD (defaults to today)
            billable: Whether this time is billable (default True)

        Returns:
            TimeActivity object or None if failed
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        # Convert hours to hours and minutes for QBO
        total_minutes = int(hours * 60)
        qbo_hours = total_minutes // 60
        qbo_minutes = total_minutes % 60

        time_activity = {
            'NameOf': 'Employee',
            'EmployeeRef': {'value': employee_id},
            'TxnDate': date,
            'Hours': qbo_hours,
            'Minutes': qbo_minutes,
            'BillableStatus': 'Billable' if billable else 'NotBillable'
        }

        # Link to job/project if provided
        if job_number:
            project = self.find_project_by_name(job_number)
            if project:
                time_activity['CustomerRef'] = {'value': project['Id']}
            else:
                self.logger.warning(f"Project {job_number} not found, time entry won't be linked to job")

        # Link to service item if provided
        if service_item_id:
            time_activity['ItemRef'] = {'value': service_item_id}

        if description:
            time_activity['Description'] = description

        result = self._make_request('POST', '/timeactivity', time_activity)

        if result and result.get('TimeActivity'):
            entry = result['TimeActivity']
            self.logger.info(f"Created time entry: {hours}h for employee {employee_id}" +
                           (f" on job {job_number}" if job_number else ""))
            return entry

        return None

    def create_field_time_entry(self, employee_name: str, field_hours: float,
                                 travel_hours: float, job_number: str,
                                 date: str = None, notes: str = None) -> dict:
        """
        Create time entries for field work - both field time and travel.

        This is the main method for syncing Data Sync field uploads to QBO.

        Args:
            employee_name: Name of field worker (e.g., "Allan")
            field_hours: Hours spent on site
            travel_hours: Travel time as entered (posted as-is, no doubling)
            job_number: Job number (e.g., "26-001")
            date: Date of work YYYY-MM-DD
            notes: Additional notes

        Returns:
            Dict with field_entry_id, travel_entry_id, and success status
        """
        result = {
            'success': False,
            'field_entry_id': None,
            'travel_entry_id': None,
            'errors': []
        }

        # Find employee
        employee = self.find_employee_by_name(employee_name)
        if not employee:
            result['errors'].append(f"Employee '{employee_name}' not found in QBO")
            return result

        employee_id = employee['Id']

        # Service item IDs (from your QBO)
        FIELD_TIME_ITEM_ID = '2'    # "Field Time" at $100/hr
        TRAVEL_ITEM_ID = '111'       # "Travel"

        # Create field time entry
        if field_hours > 0:
            description = f"Field work - {job_number}"
            if notes:
                description += f": {notes}"

            field_entry = self.create_time_entry(
                employee_id=employee_id,
                hours=field_hours,
                job_number=job_number,
                service_item_id=FIELD_TIME_ITEM_ID,
                description=description,
                date=date,
                billable=True
            )

            if field_entry:
                result['field_entry_id'] = field_entry['Id']
            else:
                result['errors'].append("Failed to create field time entry")

        # Create travel time entry (post as-is, no doubling)
        # Whatever the operator enters is the actual travel time
        if travel_hours > 0:
            travel_entry = self.create_time_entry(
                employee_id=employee_id,
                hours=travel_hours,
                job_number=job_number,
                service_item_id=TRAVEL_ITEM_ID,
                description=f"Travel - {job_number}",
                date=date,
                billable=False  # Travel typically not billable
            )

            if travel_entry:
                result['travel_entry_id'] = travel_entry['Id']
            else:
                result['errors'].append("Failed to create travel time entry")

        result['success'] = len(result['errors']) == 0
        return result

    def get_time_entries_for_job(self, job_number: str) -> list:
        """Get all time entries for a specific job."""
        # First find the project
        project = self.find_project_by_name(job_number)
        if not project:
            return []

        query = f"SELECT * FROM TimeActivity WHERE CustomerRef = '{project['Id']}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('TimeActivity'):
            return result['QueryResponse']['TimeActivity']
        return []

    def get_recent_time_entries(self, limit: int = 50) -> list:
        """Get recent time entries."""
        query = f"SELECT * FROM TimeActivity ORDER BY TxnDate DESC MAXRESULTS {limit}"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('TimeActivity'):
            return result['QueryResponse']['TimeActivity']
        return []

    # =========================================================================
    # EXPENSES (Purchase)
    # =========================================================================

    def get_accounts(self) -> list:
        """Get all accounts (for finding expense account IDs)."""
        query = "SELECT * FROM Account WHERE AccountType IN ('Expense', 'Other Expense', 'Cost of Goods Sold') MAXRESULTS 100"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('Account'):
            return result['QueryResponse']['Account']
        return []

    def find_account_by_name(self, name: str) -> Optional[Dict]:
        """Find an expense account by name (partial match)."""
        accounts = self.get_accounts()
        name_lower = name.lower()

        # Try exact match first
        for acct in accounts:
            if acct.get('Name', '').lower() == name_lower:
                return acct

        # Try partial match
        for acct in accounts:
            if name_lower in acct.get('Name', '').lower():
                return acct

        return None

    def find_or_create_vendor(self, vendor_name: str) -> Optional[str]:
        """Find or create a vendor. Returns vendor ID."""
        # Search for existing vendor
        query = f"SELECT * FROM Vendor WHERE DisplayName = '{vendor_name}'"
        result = self._make_request('GET', f"/query?query={urllib.parse.quote(query)}")

        if result and result.get('QueryResponse', {}).get('Vendor'):
            vendors = result['QueryResponse']['Vendor']
            if vendors:
                return vendors[0].get('Id')

        # Create new vendor
        vendor_data = {
            'DisplayName': vendor_name
        }

        result = self._make_request('POST', '/vendor', vendor_data)
        if result and result.get('Vendor'):
            vendor = result['Vendor']
            self.logger.info(f"Created vendor '{vendor_name}' with ID {vendor['Id']}")
            return vendor['Id']

        return None

    def create_expense(self, vendor_name: str, amount: float, account_name: str,
                       description: str = None, txn_date: str = None,
                       payment_type: str = "Cash", memo: str = None) -> Optional[Dict]:
        """
        Create an expense (Purchase) in QuickBooks.

        Args:
            vendor_name: Name of the vendor/supplier
            amount: Total expense amount
            account_name: Expense category account name (e.g., "Office Supplies")
            description: Line item description
            txn_date: Transaction date YYYY-MM-DD (defaults to today)
            payment_type: "Cash", "Check", or "CreditCard"
            memo: Additional notes for the expense

        Returns:
            Purchase object or None if failed
        """
        # Find or create vendor
        vendor_id = self.find_or_create_vendor(vendor_name)
        if not vendor_id:
            self.logger.error(f"Could not find or create vendor '{vendor_name}'")
            return None

        # Find expense account
        account = self.find_account_by_name(account_name)
        if not account:
            self.logger.error(f"Could not find expense account '{account_name}'")
            return None

        account_id = account.get('Id')

        # Need a bank/payment account for the payment
        # For Cash/CreditCard purchases, we need an account ref
        # Default to finding a checking account or credit card account
        payment_account_id = None
        if payment_type == "CreditCard":
            # Find credit card account
            cc_query = "SELECT * FROM Account WHERE AccountType = 'Credit Card' MAXRESULTS 1"
            cc_result = self._make_request('GET', f"/query?query={urllib.parse.quote(cc_query)}")
            if cc_result and cc_result.get('QueryResponse', {}).get('Account'):
                payment_account_id = cc_result['QueryResponse']['Account'][0].get('Id')
        else:
            # Find checking/bank account
            bank_query = "SELECT * FROM Account WHERE AccountType = 'Bank' MAXRESULTS 1"
            bank_result = self._make_request('GET', f"/query?query={urllib.parse.quote(bank_query)}")
            if bank_result and bank_result.get('QueryResponse', {}).get('Account'):
                payment_account_id = bank_result['QueryResponse']['Account'][0].get('Id')

        if not payment_account_id:
            self.logger.error("Could not find payment account (bank or credit card)")
            return None

        # Build purchase data
        purchase_data = {
            'PaymentType': payment_type,
            'AccountRef': {'value': payment_account_id},
            'EntityRef': {'value': vendor_id, 'type': 'Vendor'},
            'TotalAmt': amount,
            'Line': [{
                'Amount': amount,
                'DetailType': 'AccountBasedExpenseLineDetail',
                'AccountBasedExpenseLineDetail': {
                    'AccountRef': {'value': account_id}
                }
            }]
        }

        if description:
            purchase_data['Line'][0]['Description'] = description

        if txn_date:
            purchase_data['TxnDate'] = txn_date

        if memo:
            purchase_data['PrivateNote'] = memo

        result = self._make_request('POST', '/purchase', purchase_data)

        if result and result.get('Purchase'):
            purchase = result['Purchase']
            self.logger.info(f"Created expense: ${amount} to {vendor_name} ({account_name})")
            return purchase

        return None

    def get_expense_categories(self) -> list:
        """Get available expense categories/accounts for reference."""
        accounts = self.get_accounts()
        return [{'id': a.get('Id'), 'name': a.get('Name'), 'type': a.get('AccountType')}
                for a in accounts]

    # =========================================================================
    # JOB CANCELLATION SUPPORT
    # =========================================================================

    def void_invoice(self, invoice_id: str) -> bool:
        """
        Void an invoice in QBO.
        Voiding keeps the invoice in records but marks it as void (zero balance).
        """
        # First get the current invoice to get SyncToken
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            self.logger.error(f"Invoice {invoice_id} not found for voiding")
            return False

        # Void the invoice
        void_data = {
            "Id": invoice['Id'],
            "SyncToken": invoice['SyncToken']
        }

        result = self._make_request('POST', f'/invoice?operation=void', void_data)

        if result and result.get('Invoice'):
            self.logger.info(f"Voided invoice {invoice_id}")
            return True

        self.logger.error(f"Failed to void invoice {invoice_id}")
        return False

    def update_project(self, project_id: str, updates: dict) -> bool:
        """
        Update a project in QBO.

        Args:
            project_id: The QBO project ID
            updates: Dict with fields to update (e.g., {"DisplayName": "[CANCELLED] 26-011"})

        Returns:
            True if successful
        """
        # Get current project first (need SyncToken)
        project = self._make_request('GET', f'/customer/{project_id}')
        if not project or not project.get('Customer'):
            self.logger.error(f"Project {project_id} not found")
            return False

        customer = project['Customer']

        # Build update payload
        update_data = {
            "Id": customer['Id'],
            "SyncToken": customer['SyncToken'],
            "sparse": True
        }
        update_data.update(updates)

        result = self._make_request('POST', '/customer', update_data)

        if result and result.get('Customer'):
            self.logger.info(f"Updated project {project_id}")
            return True

        self.logger.error(f"Failed to update project {project_id}")
        return False

    def update_invoice_doc_number(self, invoice_id: str, doc_number: str) -> bool:
        """
        Update an invoice's DocNumber (the invoice number shown to customers).

        Used when converting an estimate to invoice - the DocNumber may need to
        be updated to match the job number format (e.g., "26-011").

        Args:
            invoice_id: The QBO invoice ID
            doc_number: The new document number (job number)

        Returns:
            True if successful
        """
        # Get current invoice first (need SyncToken)
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            self.logger.error(f"Invoice {invoice_id} not found")
            return False

        # Build update payload
        update_data = {
            "Id": invoice['Id'],
            "SyncToken": invoice['SyncToken'],
            "DocNumber": doc_number,
            "sparse": True
        }

        result = self._make_request('POST', '/invoice', update_data)

        if result and result.get('Invoice'):
            self.logger.info(f"Updated invoice {invoice_id} DocNumber to {doc_number}")
            return True

        self.logger.error(f"Failed to update invoice {invoice_id} DocNumber")
        return False
