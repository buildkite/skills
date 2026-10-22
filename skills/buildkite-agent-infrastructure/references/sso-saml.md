# SSO/SAML Configuration

Configure SSO to centralize authentication for the organization. Buildkite supports SAML 2.0 providers (Okta, Azure AD, Google Workspace, OneLogin, etc.).

## Set up a SAML provider

**Step 1 — Create the provider:**

```graphql
mutation {
  ssoProviderCreate(input: {
    organizationId: "org-id"
    type: SAML
    emailDomain: "example.com"
    emailDomainVerificationAddress: "admin@example.com"
  }) {
    ssoProvider {
      id
      state
      serviceProvider {
        metadata { url }
        ssoURL     # ACS URL — configure in IdP
        issuer     # Entity ID — configure in IdP
      }
    }
  }
}
```

**Step 2 — Configure the IdP** with the returned `ssoURL` (ACS URL) and `issuer` (Entity ID).

**Step 3 — Update with IdP metadata:**

```graphql
# Option A: Metadata URL (preferred — auto-updates)
mutation {
  ssoProviderUpdate(input: {
    id: "sso-provider-id"
    identityProvider: {
      metadata: { url: "https://idp.example.com/saml/metadata" }
    }
  }) {
    ssoProvider { id state }
  }
}

# Option B: Manual configuration
mutation {
  ssoProviderUpdate(input: {
    id: "sso-provider-id"
    identityProvider: {
      ssoURL: "https://idp.example.com/saml/sso"
      issuer: "https://idp.example.com"
      certificate: "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
    }
  }) {
    ssoProvider { id state }
  }
}
```

**Step 4 — Verify the email domain** (Buildkite sends a verification email to the address specified).

**Step 5 — Enable the provider** once verification completes and IdP is configured.

## Query SSO providers

```graphql
query {
  organization(slug: "my-org") {
    ssoProviders(first: 10) {
      edges {
        node {
          id
          type
          state
          emailDomain
          enabledAt
          ... on SSOProviderSAML {
            identityProvider { ssoURL issuer certificate metadata { url xml } }
          }
          ... on SSOProviderGoogleGSuite {
            googleHostedDomain
          }
        }
      }
    }
  }
}
```

Provider states: `PENDING` (created, awaiting config), `DISABLED` (configured but off), `ENABLED` (active).
