using System;
using System.Runtime.InteropServices;
using Microsoft.VisualStudio.Shell;

namespace Aegis.LocalAgent.VisualStudio.ToolWindows
{
    [Guid(Guids.ToolWindowGuidString)]
    public sealed class AegisToolWindow : ToolWindowPane
    {
        public AegisToolWindow() : base(null)
        {
            Caption = "Aegis Local Agent";
            Content = new AegisToolWindowControl();
        }
    }
}
