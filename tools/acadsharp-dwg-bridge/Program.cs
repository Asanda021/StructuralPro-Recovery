using ACadSharp.IO;

if (args.Length != 2)
{
    Console.Error.WriteLine("Usage: StructuralPro.DwgBridge <input.dwg> <output.dxf>");
    return 2;
}

var input = Path.GetFullPath(args[0]);
var output = Path.GetFullPath(args[1]);

if (!File.Exists(input) || !input.EndsWith(".dwg", StringComparison.OrdinalIgnoreCase))
{
    Console.Error.WriteLine("Input must be an existing .dwg file.");
    return 3;
}

Directory.CreateDirectory(Path.GetDirectoryName(output)!);

try
{
    using var reader = new DwgReader(input);
    reader.OnNotification += (_, e) =>
        Console.Error.WriteLine($"[{e.NotificationType}] {e.Message}");

    var document = reader.Read();

    using var writer = new DxfWriter(output, document, false);
    writer.Write();

    if (!File.Exists(output) || new FileInfo(output).Length == 0)
    {
        Console.Error.WriteLine("ACadSharp produced no DXF artifact.");
        return 4;
    }

    return 0;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"ACadSharp DWG read/conversion failed: {ex}");
    return 10;
}
