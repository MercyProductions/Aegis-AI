import { useState, type FormEvent } from 'react';
import { ArrowRight, Brain, CheckCircle2, Code, Lock, Mail, Shield, Sparkles, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { brandAssets } from '../brandAssets';
import type { AuthLoginRequest, AuthRegisterRequest } from '../types';

type PublicSiteProps = {
  routePath: string;
  authLoading: boolean;
  authStatus: string;
  onNavigate: (path: string) => void;
  onLogin: (request: AuthLoginRequest) => Promise<void>;
  onRegister: (request: AuthRegisterRequest) => Promise<void>;
  onForgotPassword: (email: string) => Promise<void>;
};

const navItems = [
  ['/', 'Home'],
  ['/features', 'Features'],
  ['/pricing', 'Pricing'],
  ['/about', 'About'],
  ['/security', 'Security'],
  ['/contact', 'Contact']
];

const featureCards: Array<[string, string, LucideIcon]> = [
  ['Coding Workspace', 'Plan, edit, validate, repair, and ship project work with checkpoints and task continuity.', Code],
  ['Workflow Orchestration', 'Turn complex requests into tracked tasks, approvals, validation, repair attempts, and outcomes.', Zap],
  ['Memory + Intelligence', 'Preserve project knowledge, preferences, recurring fixes, architecture maps, and research context.', Brain],
  ['Creative Studio', 'Organize image, video, voice, beat, and asset generation jobs in the same local-first runtime.', Sparkles],
  ['Automation Runtime', 'Coordinate triggers, actions, schedules, agents, and background intelligence with permission gates.', CheckCircle2],
  ['Security Foundation', 'Keep execution observable, approval-aware, checkpointed, reversible, and privacy-conscious.', Shield]
];

const useCases = [
  'AI coding and refactor sessions',
  'Project intelligence and architecture memory',
  'Validation, repair, and rollback workflows',
  'Creative asset generation for apps and launches',
  'Research sessions and reusable workflow knowledge',
  'Local model routing and privacy-aware execution'
];

export function PublicSite({
  routePath,
  authLoading,
  authStatus,
  onNavigate,
  onLogin,
  onRegister,
  onForgotPassword
}: PublicSiteProps) {
  const page = routePath.replace(/\/+$/, '') || '/';

  return (
    <div className="public-site-shell">
      <div className="public-site-glow" />
      <header className="public-nav">
        <button type="button" className="public-brand" onClick={() => onNavigate('/')}>
          <span className="public-brand-mark">
            <img className="public-brand-mark-image" src={brandAssets.mark} alt="" aria-hidden="true" />
          </span>
          <span>
            <strong>Auralith OS</strong>
            <small>Powered by Aegis Core</small>
          </span>
        </button>

        <nav className="public-nav-links" aria-label="Public website navigation">
          {navItems.map(([path, label]) => (
            <button
              key={path}
              type="button"
              className={page === path ? 'public-nav-link is-active' : 'public-nav-link'}
              onClick={() => onNavigate(path)}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="public-nav-actions">
          <button type="button" className="public-link-button" onClick={() => onNavigate('/login')}>
            Login
          </button>
          <button type="button" className="public-primary-button" onClick={() => onNavigate('/register')}>
            Get Started
          </button>
        </div>
      </header>

      <main>
        {page === '/login' ? (
          <AuthPanel mode="login" loading={authLoading} status={authStatus} onLogin={onLogin} onNavigate={onNavigate} />
        ) : page === '/register' ? (
          <AuthPanel
            mode="register"
            loading={authLoading}
            status={authStatus}
            onRegister={onRegister}
            onNavigate={onNavigate}
          />
        ) : page === '/forgot-password' ? (
          <ForgotPasswordPanel
            loading={authLoading}
            status={authStatus}
            onForgotPassword={onForgotPassword}
            onNavigate={onNavigate}
          />
        ) : page === '/features' ? (
          <FeaturesPage onNavigate={onNavigate} />
        ) : page === '/pricing' ? (
          <PricingPage onNavigate={onNavigate} />
        ) : page === '/about' ? (
          <AboutPage />
        ) : page === '/security' ? (
          <SecurityPage onNavigate={onNavigate} />
        ) : page === '/contact' ? (
          <ContactPage />
        ) : (
          <HomePage onNavigate={onNavigate} />
        )}
      </main>
    </div>
  );
}

function HomePage({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <>
      <section className="public-hero">
        <div className="public-hero-copy">
          <span className="public-eyebrow">Local-first. Premium. Runtime-driven.</span>
          <h1>Auralith OS &mdash; Your Local-First AI Operating Environment</h1>
          <p>
            Code, automate, research, create, and orchestrate from one persistent intelligent environment.
          </p>
          <div className="public-hero-actions">
            <button type="button" className="public-primary-button public-large-button" onClick={() => onNavigate('/register')}>
              Get Started
              <ArrowRight size={18} />
            </button>
            <button type="button" className="public-secondary-button public-large-button" onClick={() => onNavigate('/features')}>
              View Features
            </button>
            <button type="button" className="public-link-button public-large-button" onClick={() => onNavigate('/login')}>
              Login
            </button>
          </div>
        </div>
        <ProductMockup />
      </section>

      <FeatureGrid title="One runtime for serious AI work" />
      <HowItWorks />
      <UseCases />
      <SecurityBand onNavigate={onNavigate} />
      <PricingPreview onNavigate={onNavigate} />
      <FinalCta onNavigate={onNavigate} />
    </>
  );
}

function FeaturesPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <div className="public-page-stack">
      <PageIntro
        eyebrow="Capabilities"
        title="A cohesive AI environment, not another pile of tools."
        text="Auralith OS combines coding, agents, memory, validation, automation, research, creative assets, and workflow orchestration behind one protected workspace."
      />
      <FeatureGrid title="Core systems" />
      <section className="public-band">
        <h2>Built around workflows</h2>
        <p>
          Every serious action can flow through tasks, approvals, checkpoints, validation, repair, telemetry, and final summaries.
        </p>
        <button type="button" className="public-primary-button" onClick={() => onNavigate('/register')}>
          Create Account
        </button>
      </section>
    </div>
  );
}

function PricingPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <div className="public-page-stack">
      <PageIntro
        eyebrow="Pricing"
        title="Start local. Scale only when you need it."
        text="Auralith OS is designed as a local-first operating environment with plans that can grow into remote workers, shared intelligence, and organization policy."
      />
      <div className="public-pricing-grid">
        <PricingCard name="Local" price="$0" detail="For individual local-first workspaces." items={['Local runtime', 'Protected workspace', 'Project memory', 'Task tracking']} />
        <PricingCard name="Pro" price="$19" detail="For daily AI engineering workflows." items={['Advanced agents', 'Creative Studio jobs', 'Long-running tasks', 'Priority routing profiles']} highlighted />
        <PricingCard name="Team" price="Custom" detail="For shared intelligence and policy." items={['Org controls', 'Shared workflows', 'Audit trails', 'Distributed workers']} />
      </div>
      <FinalCta onNavigate={onNavigate} />
    </div>
  );
}

function AboutPage() {
  return (
    <div className="public-page-stack">
      <PageIntro
        eyebrow="About"
        title="Auralith OS is built for trust, continuity, and disciplined capability."
        text="The product direction is not infinite feature sprawl. Auralith OS is meant to become a calm, powerful environment people can rely on every day."
      />
      <section className="public-split-band">
        <div>
          <h2>Product philosophy</h2>
          <p>
            Auralith OS prioritizes local-first control, explainable autonomy, reliable workflows, durable memory, rollback safety, and premium interaction quality.
          </p>
        </div>
        <div className="public-principle-list">
          {['Reliability over novelty', 'Clarity over feature count', 'Workflows over dashboards', 'Trust over aggression'].map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </section>
    </div>
  );
}

function SecurityPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <div className="public-page-stack">
      <PageIntro
        eyebrow="Security"
        title="Local-first by default, permission-aware by design."
        text="Auralith OS keeps user control at the center: approvals, checkpoints, auditability, protected workspace zones, and transparent execution boundaries."
      />
      <SecurityBand onNavigate={onNavigate} />
      <FeatureGrid title="Safety surfaces" />
    </div>
  );
}

function ContactPage() {
  return (
    <div className="public-page-stack">
      <PageIntro
        eyebrow="Contact"
        title="Talk to the Aegis team behind Auralith OS."
        text="For product feedback, collaboration, enterprise deployments, or security questions, use the contact channel below."
      />
      <section className="public-contact-card">
        <Mail size={26} />
        <div>
          <h2>Contact</h2>
          <p>hello@aegis.local</p>
        </div>
      </section>
    </div>
  );
}

function ProductMockup() {
  return (
    <div className="public-product-mockup" aria-label="Auralith OS workspace product mockup">
      <div className="mockup-sidebar">
        <span className="mockup-sidebar-brand">
          <img src={brandAssets.mark} alt="" aria-hidden="true" />
        </span>
        <span />
        <span />
        <span />
      </div>
      <div className="mockup-main">
        <div className="mockup-topbar" />
        <div className="mockup-workspace">
          <div className="mockup-brand-showcase">
            <img src={brandAssets.banner} alt="Auralith OS" />
          </div>
          <div className="mockup-command">
            <Sparkles size={18} />
            <span>Auralith Prime is preparing your workspace...</span>
          </div>
          <div className="mockup-grid">
            <span />
            <span />
            <span />
          </div>
        </div>
      </div>
      <div className="mockup-panel">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function FeatureGrid({ title }: { title: string }) {
  return (
    <section className="public-section">
      <h2>{title}</h2>
      <div className="public-feature-grid">
        {featureCards.map(([title, text, Icon]) => (
          <article className="public-feature-card" key={String(title)}>
            <span className="public-feature-icon">
              <Icon size={20} />
            </span>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="public-section">
      <h2>How it works</h2>
      <div className="public-steps">
        {['Create a protected account', 'Connect your local workspace', 'Run tasks through Auralith Prime', 'Validate, repair, and remember outcomes'].map((item, index) => (
          <article key={item}>
            <span>{index + 1}</span>
            <h3>{item}</h3>
          </article>
        ))}
      </div>
    </section>
  );
}

function UseCases() {
  return (
    <section className="public-section">
      <h2>Use cases</h2>
      <div className="public-use-case-grid">
        {useCases.map((item) => (
          <span key={item}>
            <CheckCircle2 size={16} />
            {item}
          </span>
        ))}
      </div>
    </section>
  );
}

function SecurityBand({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <section className="public-security-band">
      <div>
        <span className="public-feature-icon">
          <Lock size={20} />
        </span>
        <h2>Designed for local-first control</h2>
        <p>
          The public website stays separate from the protected Auralith OS workspace. Sensitive project work lives behind login and continues to use existing approval, checkpoint, validation, and rollback systems.
        </p>
      </div>
      <button type="button" className="public-secondary-button" onClick={() => onNavigate('/security')}>
        Security Details
      </button>
    </section>
  );
}

function PricingPreview({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <section className="public-section">
      <h2>Simple path into the workspace</h2>
      <div className="public-pricing-preview">
        <strong>Local-first access</strong>
        <span>Protected Auralith OS shell, memory, tasks, models, agents, creative workflows, and observability.</span>
        <button type="button" className="public-primary-button" onClick={() => onNavigate('/pricing')}>
          View Pricing
        </button>
      </div>
    </section>
  );
}

function FinalCta({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <section className="public-final-cta">
      <h2>Enter Auralith OS when you are ready to work.</h2>
      <p>Create an account, then open the protected Auralith OS operating environment.</p>
      <div className="public-hero-actions">
        <button type="button" className="public-primary-button public-large-button" onClick={() => onNavigate('/register')}>
          Get Started
        </button>
        <button type="button" className="public-secondary-button public-large-button" onClick={() => onNavigate('/login')}>
          Login
        </button>
      </div>
    </section>
  );
}

function PageIntro({ eyebrow, title, text }: { eyebrow: string; title: string; text: string }) {
  return (
    <section className="public-page-intro">
      <span className="public-eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{text}</p>
    </section>
  );
}

function PricingCard({
  name,
  price,
  detail,
  items,
  highlighted = false
}: {
  name: string;
  price: string;
  detail: string;
  items: string[];
  highlighted?: boolean;
}) {
  return (
    <article className={highlighted ? 'public-price-card is-highlighted' : 'public-price-card'}>
      <h3>{name}</h3>
      <strong>{price}</strong>
      <p>{detail}</p>
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </article>
  );
}

function AuthPanel({
  mode,
  loading,
  status,
  onLogin,
  onRegister,
  onNavigate
}: {
  mode: 'login' | 'register';
  loading: boolean;
  status: string;
  onLogin?: (request: AuthLoginRequest) => Promise<void>;
  onRegister?: (request: AuthRegisterRequest) => Promise<void>;
  onNavigate: (path: string) => void;
}) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === 'login' && onLogin) {
      await onLogin({ email, password, remember_me: rememberMe });
    }
    if (mode === 'register' && onRegister) {
      await onRegister({ name, email, password, confirm_password: confirmPassword });
    }
  }

  return (
    <section className="public-auth-wrap">
      <form className="public-auth-card" onSubmit={submit}>
        <div className="public-auth-brand" aria-label="Auralith OS">
          <span className="public-brand-mark">
            <img className="public-brand-mark-image" src={brandAssets.mark} alt="" aria-hidden="true" />
          </span>
          <span>
            <strong>Auralith OS</strong>
            <small>Powered by Aegis Core</small>
          </span>
        </div>
        <span className="public-eyebrow">{mode === 'login' ? 'Welcome back' : 'Create account'}</span>
        <h1>{mode === 'login' ? 'Login to Auralith OS' : 'Register for Auralith OS'}</h1>
        <p>The full Auralith OS workspace opens only after authentication.</p>

        {mode === 'register' ? (
          <label>
            <span>Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
          </label>
        ) : null}

        <label>
          <span>Email</span>
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>

        <label>
          <span>Password</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={mode === 'register' ? 8 : 1} />
        </label>

        {mode === 'register' ? (
          <label>
            <span>Confirm Password</span>
            <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required minLength={8} />
          </label>
        ) : (
          <div className="public-auth-row">
            <label className="public-checkbox-row">
              <input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} />
              <span>Remember me</span>
            </label>
            <button type="button" className="public-link-button" onClick={() => onNavigate('/forgot-password')}>
              Forgot password?
            </button>
          </div>
        )}

        <button type="submit" className="public-primary-button public-full-button" disabled={loading}>
          {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}
        </button>

        {status ? <div className="public-auth-status">{status}</div> : null}

        <button
          type="button"
          className="public-link-button"
          onClick={() => onNavigate(mode === 'login' ? '/register' : '/login')}
        >
          {mode === 'login' ? 'Need an account? Register' : 'Already have an account? Login'}
        </button>
      </form>
    </section>
  );
}

function ForgotPasswordPanel({
  loading,
  status,
  onForgotPassword,
  onNavigate
}: {
  loading: boolean;
  status: string;
  onForgotPassword: (email: string) => Promise<void>;
  onNavigate: (path: string) => void;
}) {
  const [email, setEmail] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onForgotPassword(email);
  }

  return (
    <section className="public-auth-wrap">
      <form className="public-auth-card" onSubmit={submit}>
        <div className="public-auth-brand" aria-label="Auralith OS">
          <span className="public-brand-mark">
            <img className="public-brand-mark-image" src={brandAssets.mark} alt="" aria-hidden="true" />
          </span>
          <span>
            <strong>Auralith OS</strong>
            <small>Powered by Aegis Core</small>
          </span>
        </div>
        <span className="public-eyebrow">Recovery</span>
        <h1>Reset password</h1>
        <p>Enter your email to start password recovery when outbound email is configured.</p>
        <label>
          <span>Email</span>
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <button type="submit" className="public-primary-button public-full-button" disabled={loading}>
          {loading ? 'Please wait...' : 'Request reset'}
        </button>
        {status ? <div className="public-auth-status">{status}</div> : null}
        <button type="button" className="public-link-button" onClick={() => onNavigate('/login')}>
          Back to login
        </button>
      </form>
    </section>
  );
}
