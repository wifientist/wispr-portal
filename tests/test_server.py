import pytest
from unittest.mock import patch, MagicMock
from server import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


# --- Homepage ---

def test_homepage_returns_200(client):
    resp = client.get('/')
    assert resp.status_code == 200


def test_homepage_serves_html(client):
    resp = client.get('/')
    assert b'<!DOCTYPE html>' in resp.data or b'<html' in resp.data


def test_homepage_with_query_params(client):
    resp = client.get('/?client_mac=ABC&nbiIP=test.ruckus.cloud')
    assert resp.status_code == 200


# --- CORS ---

def test_cors_headers_present(client):
    resp = client.get('/')
    assert 'Access-Control-Allow-Origin' in resp.headers
    assert 'Access-Control-Allow-Methods' in resp.headers


def test_options_preflight(client):
    resp = client.options('/api/authenticate')
    assert resp.status_code == 200


# --- Validation errors ---

def test_missing_integration_key(client):
    resp = client.post('/api/authenticate', json={
        'authMode': 'always-accept',
        'nbiIP': 'test.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
    })
    assert resp.status_code == 400
    assert b'Missing integration key' in resp.data


def test_missing_nbi_ip(client):
    resp = client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'always-accept',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
    })
    assert resp.status_code == 400
    assert b'nbiIP' in resp.data


def test_missing_client_mac(client):
    resp = client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'always-accept',
        'nbiIP': 'test.ruckus.cloud',
    })
    assert resp.status_code == 400
    assert b'clientMac' in resp.data


def test_credentials_mode_missing_username(client):
    resp = client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'credentials',
        'nbiIP': 'test.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
        'clientIP': '10.0.0.1',
        'password': 'pass',
    })
    assert resp.status_code == 400
    assert b'Username and password required' in resp.data


def test_credentials_mode_missing_password(client):
    resp = client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'credentials',
        'nbiIP': 'test.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
        'clientIP': '10.0.0.1',
        'username': 'user',
    })
    assert resp.status_code == 400
    assert b'Username and password required' in resp.data


# --- Successful auth (mocked RUCKUS API) ---

RUCKUS_SUCCESS = {
    'Vendor': 'Ruckus',
    'APIVersion': '1.0',
    'ResponseCode': 201,
    'ReplyMessage': 'Login succeeded',
}


@patch('server.requests.post')
def test_always_accept_success(mock_post, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = RUCKUS_SUCCESS
    mock_post.return_value = mock_resp

    resp = client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'always-accept',
        'nbiIP': 'test.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ruckusApiResponse']['ResponseCode'] == 201
    assert data['ruckusApiRequest']['RequestType'] == 'Authorize'
    assert data['ruckusApiRequest']['RequestPassword'] == '***HIDDEN***'


@patch('server.requests.post')
def test_credentials_mode_success(mock_post, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = RUCKUS_SUCCESS
    mock_post.return_value = mock_resp

    resp = client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'credentials',
        'nbiIP': 'test.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
        'clientIP': '10.0.0.1',
        'username': 'user@test.com',
        'password': 'secret',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ruckusApiRequest']['RequestType'] == 'Login'
    assert data['ruckusApiRequest']['UE-Username'] == 'user@test.com'
    assert data['ruckusApiRequest'].get('UE-Password') == '***HIDDEN***'


@patch('server.requests.post')
def test_api_url_construction(mock_post, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = RUCKUS_SUCCESS
    mock_post.return_value = mock_resp

    client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'always-accept',
        'nbiIP': 'test.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
    })
    called_url = mock_post.call_args[0][0]
    assert called_url == 'https://test.ruckus.cloud/portalintf'


@patch('server.requests.post')
def test_api_url_preserves_existing_scheme(mock_post, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = RUCKUS_SUCCESS
    mock_post.return_value = mock_resp

    client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'always-accept',
        'nbiIP': 'https://already-has-scheme.ruckus.cloud/portalintf',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
    })
    called_url = mock_post.call_args[0][0]
    assert called_url == 'https://already-has-scheme.ruckus.cloud/portalintf'


# --- Error handling ---

@patch('server.requests.post')
def test_ruckus_api_connection_error(mock_post, client):
    import requests as req
    mock_post.side_effect = req.exceptions.ConnectionError('Connection refused')

    resp = client.post('/api/authenticate', json={
        'integrationKey': 'test-key',
        'authMode': 'always-accept',
        'nbiIP': 'unreachable.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
    })
    assert resp.status_code == 500
    assert b'Failed to connect' in resp.data


@patch('server.requests.post')
def test_ruckus_login_failed_response(mock_post, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        'Vendor': 'Ruckus',
        'APIVersion': '1.0',
        'ResponseCode': 301,
        'ReplyMessage': 'Login failed',
    }
    mock_post.return_value = mock_resp

    resp = client.post('/api/authenticate', json={
        'integrationKey': 'bad-key',
        'authMode': 'always-accept',
        'nbiIP': 'test.ruckus.cloud',
        'clientMac': 'AA:BB:CC:DD:EE:FF',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ruckusApiResponse']['ResponseCode'] == 301
