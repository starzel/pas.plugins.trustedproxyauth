"""Class: TrustedproxyHelper
"""
import re
import logging
from AccessControl.SecurityInfo import ClassSecurityInfo
from App.class_init import default__class_init__ as InitializeClass
from OFS.Cache import Cacheable
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.utils import classImplements
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from socket import getaddrinfo, herror

logger = logging.getLogger('pas.plugins.trustedproxy')

IS_IP = re.compile("^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])"
                   "(\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])){3}$")


manage_addTrustedProxyPlugin = PageTemplateFile("templates/addPlugin",
    globals(), __name__="manage_addPlugin")

def addTrustedProxyPlugin(self, id, title="", user_model=None, group_model=None, REQUEST=None):
    """Add an SQLAlchemy plugin to a PAS."""
    p=TrustedProxyPlugin(id, title)
    p.user_model=user_model
    p.group_model=group_model
    self._setObject(p.getId(), p)

    if REQUEST is not None:
        REQUEST.response.redirect("%s/manage_workspace"
                "?manage_tabs_message=SQLAlchemy+plugin+added." %
                self.absolute_url())


class TrustedProxyPlugin(BasePlugin, Cacheable):
    """
    """

    meta_type = 'Trusted proxy authentication'
    security = ClassSecurityInfo()

    _properties = BasePlugin._properties + (
            { 'id'    : 'trusted_proxies',
              'label' : 'IP addresses of trusted proxies',
              'type'  : 'lines',
              'mode'  : 'w',
            },
            { 'id'    : 'login_header',
              'label' : 'HTTP header containing the login name',
              'type'  : 'string',
              'mode'  : 'w',
            },
    )


    def __init__(self, id, title=None):
        self._setId( id )
        self.title = title

    security.declarePrivate('authenticateCredentials')
    def authenticateCredentials(self, credentials):
        """Authenticate Credentials for Trusted Proxy
        """
        trusted_proxies = list(self.getProperty('trusted_proxies', ()))
        login = credentials.get('login')
        extractor = credentials.get('extractor')
        uid = credentials.get('id')
        remote_address = credentials.get('remote_address')
        remote_host = credentials.get('remote_host')

        if not trusted_proxies:
            logger.warn('authenticateCredentials ignoring request '
                        'because trusted_proxies is not configured')
            return None

        if (not login or extractor != self.getId()):
            logger.warn('authenticateCredentials ignoring request '
                        'from %r for %r/%r', extractor, uid, login)
            return None

        for idx, addr in enumerate(trusted_proxies):
            if IS_IP.match(addr):
                continue
            # If it's not an IP, then it's a hostname, and we need to
            # resolve it to an IP.
            try:
                # XXX Should we cache calls to getaddrinfo? Supposedly
                # it can be quite expensive for a 'DNS Miss'.
                trusted_proxies[idx+1:idx+1] = [t[-1][0] for t in getaddrinfo(addr, None)]
            except herror:
                logger.debug('Could not resolve hostname to address: %r', addr)

        for addr in (remote_address, remote_host):
            if addr in trusted_proxies:
                logger.debug('trusted user is %r:%r/%r', 
                             addr, uid, login)
                return uid, login

        logger.warn('authenticateCredentials ignoring request '
                    'from %r - not in the list of trusted proxies (%r)',
                    (remote_address, remote_host), trusted_proxies)
        return None


    def extractCredentials(self, request):
        """Extract Credentials for Trusted Proxy
        """
        creds = {}
        login_header = self.getProperty('login_header', 'X_REMOTE_USER')
        login = request.get_header(login_header, '')

        # We need the IP of the Proxy, not the real client ip, thus we
        # can't use request.getClientAddr()
        remote_address = request.get('REMOTE_ADDR', '')

        if login and remote_address:
            # `login` and `id` might be overriden below.
            creds['id'] = login
            creds['login'] = login
            creds['remote_address'] = remote_address
            creds['remote_host'] = request.get_header('REMOTE_HOST', '')

            logger.debug('extractCredentials has %r:%r',
                         remote_address, login)

        return creds



classImplements(TrustedProxyPlugin, IAuthenticationPlugin)

InitializeClass(TrustedProxyPlugin)