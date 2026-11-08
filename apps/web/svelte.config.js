import adapter from '@sveltejs/adapter-static';
export default { kit: { adapter: adapter({ fallback: 'index.html' }), csp: { mode: 'hash', directives: { 'default-src': ['self'], 'script-src': ['self'], 'style-src': ['self', 'unsafe-inline'], 'img-src': ['self', 'data:'], 'connect-src': ['self'], 'object-src': ['none'], 'base-uri': ['self'] } } } };
