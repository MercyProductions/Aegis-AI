using System;
using System.Runtime.InteropServices;
using System.Threading;
using Aegis.LocalAgent.VisualStudio.Commands;
using Aegis.LocalAgent.VisualStudio.Options;
using Aegis.LocalAgent.VisualStudio.Services;
using Aegis.LocalAgent.VisualStudio.ToolWindows;
using Microsoft.VisualStudio;
using Microsoft.VisualStudio.Shell;
using Microsoft.VisualStudio.Shell.Interop;

namespace Aegis.LocalAgent.VisualStudio
{
    [PackageRegistration(UseManagedResourcesOnly = true, AllowsBackgroundLoading = true)]
    [ProvideBindingPath]
    [Guid(Guids.PackageGuidString)]
    [InstalledProductRegistration("Aegis Local Agent", "Local Ollama coding agent for Visual Studio solutions", "0.1.1")]
    [ProvideMenuResource("Menus.ctmenu", 1)]
    [ProvideToolWindow(typeof(AegisToolWindow))]
    [ProvideAutoLoad(VSConstants.UICONTEXT.SolutionExists_string, PackageAutoLoadFlags.BackgroundLoad)]
    [ProvideOptionPage(typeof(AegisOptionsPage), "Aegis Local Agent", "General", 0, 0, true)]
    public sealed class AegisPackage : AsyncPackage
    {
        private IVsSolution solutionService;
        private uint solutionEventsCookie;
        private SolutionEventsListener solutionEvents;

        protected override async System.Threading.Tasks.Task InitializeAsync(CancellationToken cancellationToken, IProgress<ServiceProgressData> progress)
        {
            await JoinableTaskFactory.SwitchToMainThreadAsync(cancellationToken);

            var runtime = new AegisAgentRuntime(this);
            AegisAgentRuntime.SetCurrent(runtime);
            await AegisCommands.InitializeAsync(this, runtime);

            solutionService = await GetServiceAsync(typeof(SVsSolution)) as IVsSolution;
            if (solutionService != null)
            {
                solutionEvents = new SolutionEventsListener(runtime);
                solutionService.AdviseSolutionEvents(solutionEvents, out solutionEventsCookie);
            }

#pragma warning disable VSSDK007
            if (runtime.ShouldAutoScanSolutions())
            {
                JoinableTaskFactory.RunAsync(async () => await runtime.RescanSolutionIntelligenceAsync(showWindow: false))
                    .FileAndForget("AegisLocalAgent/InitialSolutionScan");
            }
#pragma warning restore VSSDK007
        }

        protected override void Dispose(bool disposing)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            if (disposing && solutionService != null && solutionEventsCookie != 0)
            {
                solutionService.UnadviseSolutionEvents(solutionEventsCookie);
                solutionEventsCookie = 0;
            }

            base.Dispose(disposing);
        }

        private sealed class SolutionEventsListener : IVsSolutionEvents
        {
            private readonly AegisAgentRuntime runtime;

            public SolutionEventsListener(AegisAgentRuntime runtime)
            {
                this.runtime = runtime;
            }

            public int OnAfterOpenSolution(object pUnkReserved, int fNewSolution)
            {
#pragma warning disable VSSDK007
                if (runtime.ShouldAutoScanSolutions())
                {
                    ThreadHelper.JoinableTaskFactory.RunAsync(async () => await runtime.RescanSolutionIntelligenceAsync(showWindow: false))
                        .FileAndForget("AegisLocalAgent/SolutionOpened");
                }
#pragma warning restore VSSDK007
                return VSConstants.S_OK;
            }

            public int OnAfterCloseSolution(object pUnkReserved) => VSConstants.S_OK;
            public int OnAfterLoadProject(IVsHierarchy pStubHierarchy, IVsHierarchy pRealHierarchy) => VSConstants.S_OK;
            public int OnAfterOpenProject(IVsHierarchy pHierarchy, int fAdded) => VSConstants.S_OK;
            public int OnBeforeCloseProject(IVsHierarchy pHierarchy, int fRemoved) => VSConstants.S_OK;
            public int OnBeforeCloseSolution(object pUnkReserved) => VSConstants.S_OK;
            public int OnBeforeUnloadProject(IVsHierarchy pRealHierarchy, IVsHierarchy pStubHierarchy) => VSConstants.S_OK;
            public int OnQueryCloseProject(IVsHierarchy pHierarchy, int fRemoving, ref int pfCancel) => VSConstants.S_OK;
            public int OnQueryCloseSolution(object pUnkReserved, ref int pfCancel) => VSConstants.S_OK;
            public int OnQueryUnloadProject(IVsHierarchy pRealHierarchy, ref int pfCancel) => VSConstants.S_OK;
        }
    }
}
