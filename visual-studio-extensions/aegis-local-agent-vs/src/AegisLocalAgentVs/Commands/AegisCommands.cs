using System;
using System.ComponentModel.Design;
using System.Threading.Tasks;
using Aegis.LocalAgent.VisualStudio.Services;
using Microsoft.VisualStudio.Shell;

namespace Aegis.LocalAgent.VisualStudio.Commands
{
    internal sealed class AegisCommands
    {
        private readonly AsyncPackage package;
        private readonly AegisAgentRuntime runtime;

        private AegisCommands(AsyncPackage package, AegisAgentRuntime runtime)
        {
            this.package = package;
            this.runtime = runtime;
        }

        public static async Task InitializeAsync(AsyncPackage package, AegisAgentRuntime runtime)
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var commandService = await package.GetServiceAsync(typeof(IMenuCommandService)) as OleMenuCommandService;
            if (commandService == null)
            {
                return;
            }

            var commands = new AegisCommands(package, runtime);
            commands.Register(commandService, CommandIds.OpenAgent, () => runtime.ShowToolWindowAsync());
            commands.Register(commandService, CommandIds.ExplainCurrentFile, () => runtime.ExplainCurrentFileAsync());
            commands.Register(commandService, CommandIds.ReviewSelectedCode, () => runtime.ReviewSelectedCodeAsync());
            commands.Register(commandService, CommandIds.FixBuildErrors, () => runtime.FixBuildErrorsAsync());
            commands.Register(commandService, CommandIds.GenerateRoadmap, () => runtime.GenerateRoadmapAsync());
            commands.Register(commandService, CommandIds.ContinueFromRoadmap, () => runtime.ContinueFromRoadmapAsync());
            commands.Register(commandService, CommandIds.RunHealthCheck, () => runtime.RunHealthCheckAsync());
            commands.Register(commandService, CommandIds.FixSelectedError, () => runtime.FixSelectedErrorAsync());
            commands.Register(commandService, CommandIds.ExplainBuildFailure, () => runtime.ExplainBuildFailureAsync());
            commands.Register(commandService, CommandIds.ReviewStartupProject, () => runtime.ReviewStartupProjectAsync());
            commands.Register(commandService, CommandIds.GenerateSolutionRoadmap, () => runtime.GenerateRoadmapAsync());
            commands.Register(commandService, CommandIds.ContinueCurrentSolution, () => runtime.ContinueCurrentSolutionAsync());
            commands.Register(commandService, CommandIds.RollbackLastChange, () => runtime.RollbackLastChangeAsync());
            commands.Register(commandService, CommandIds.RefactorSelectedCode, () => runtime.RefactorSelectedCodeAsync());
            commands.Register(commandService, CommandIds.RescanSolutionIntelligence, () => runtime.RescanSolutionIntelligenceAsync());
            commands.Register(commandService, CommandIds.ExplainThisFile, () => runtime.ExplainSelectedExplorerFileAsync());
            commands.Register(commandService, CommandIds.ReviewThisProject, () => runtime.ReviewSelectedProjectAsync());
            commands.Register(commandService, CommandIds.FixErrorsInThisProject, () => runtime.FixErrorsInSelectedProjectAsync());
            commands.Register(commandService, CommandIds.GenerateTestsForThisFile, () => runtime.GenerateTestsForSelectedExplorerFileAsync());
            commands.Register(commandService, CommandIds.AddFeatureToThisProject, () => runtime.AddFeatureToSelectedProjectAsync());
            commands.Register(commandService, CommandIds.CreateRoadmapFromSolution, () => runtime.GenerateRoadmapAsync());
        }

        private void Register(OleMenuCommandService commandService, int commandId, Func<Task> handler)
        {
            var id = new CommandID(new Guid(Guids.CommandSetGuidString), commandId);
            var command = new OleMenuCommand((_, __) =>
            {
#pragma warning disable VSSDK007
                ThreadHelper.JoinableTaskFactory.RunAsync(async () =>
                {
                    try
                    {
                        await handler();
                    }
                    catch (Exception ex)
                    {
                        await runtime.ReportErrorAsync(ex);
                    }
                }).FileAndForget("AegisLocalAgent/Command");
#pragma warning restore VSSDK007
            }, id);
            commandService.AddCommand(command);
        }
    }
}
