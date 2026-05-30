
from datetime import date
from rich.console import Console
from rich.table import Table
from rich.box import ROUNDED
from typing import Annotated, Optional

import humanize
import plantera.db as db
import plantera.service as service
import subprocess
import sys
import typer

console = Console()
app = typer.Typer(add_completion=False)

__version__ = "1.0.0"

BANNER = """[green]
  __
 /  \\    ██████╗ ██╗      █████╗ ███╗   ██╗████████╗███████╗██████╗  █████╗
/    \\   ██╔══██╗██║     ██╔══██╗████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗
\\ ~~ /   ██████╔╝██║     ███████║██╔██╗ ██║   ██║   █████╗  ██████╔╝███████║
 \\  /    ██╔═══╝ ██║     ██╔══██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔══██║
  \\/     ██║     ███████╗██║  ██║██║ ╚████║   ██║   ███████╗██║  ██║██║  ██║
  ||     ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
  ||
[/green]"""

ALLOWED_SETTINGS = ["auto_interval", "claude_api_key"]

def version_callback(value: bool) -> None:
  """
  Callback for the --version flag. Prints the version and exits.

  Parameters
  ----------
  value : bool
      True if --version was passed.
  """
  if value:
    typer.echo(f"Plantera v{__version__}")
    raise typer.Exit()


@app.callback(invoke_without_command=True)
def startup(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True, help="Show version and exit.")
) -> None:
  """Initialize the database on startup."""

  # Show banner on first run
  first_run = not db.DB_PATH.exists()

  result = db.db_init()
  if result not in [True, None]:
    typer.echo(f"Error initializing database: {str(result)}")
    raise typer.Exit(code=1)

  if first_run:
    Console().print(BANNER, highlight=False)

  if ctx.invoked_subcommand is None:
    Console().print("[dark_orange]Usage:[/dark_orange] [green]plantera[/green] <command>")
    Console().print("Try '[green]plantera[/green] [cornflower_blue]--help[/cornflower_blue]' for more information.")
    raise typer.Exit()


@app.command()
def add(
    nickname: Annotated[str, typer.Argument(help="Name/nickname of the plant")],
    genus: Annotated[str, typer.Argument(help="Type of the plant (must exist in the plant library)")],
    last_watered: Annotated[str, typer.Argument(help="Last watered date (YYYY-MM-DD)")] = str(date.today()),
    interval: Annotated[int, typer.Argument(help="Watering interval (in days)")] = 7,
    environment: Annotated[str, typer.Argument(help="Description of the location and physical environment of the plant")] = ''
) -> None:
  """
  Add a plant to the database.

  Parameters
  ----------
  nickname : str
      The user's name for the plant (e.g. "Bob")
  genus : str
      The genus of the plant species (must exist in plant_species table)
  last_watered : str
      Date the plant was last watered in YYYY-MM-DD format
  interval : int
      Watering interval in days
  environment : str
      Optional description of the plant's environment (e.g. "North facing window")
  """

  result = service.add_plant(nickname, genus, last_watered, interval, environment)

  if result is True:
    typer.echo(f"Plant '{nickname}' added successfully!")
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def add_species(
    genus: Annotated[str, typer.Argument(help="Genus of the plant, ie. 'Crassula' or 'Rosa")],
    common_name: Annotated[str, typer.Argument(help="Common name of the plant, ie. 'Jade' or 'Rose")],
    care_info: Annotated[str, typer.Argument(help="Care information for the plant")] = "No care information provided."
) -> None:
  """
  Add a plant species to the database.

  Parameters
  ----------
  genus : str
      The scientific genus name (e.g. "Crassula")
  common_name : str
      The common name of the plant (e.g. "Jade Plant")
  care_info : str
      Care instructions for the species
  """

  result = service.add_plant_species(genus, common_name, care_info)

  if result is True:
    typer.echo(f"Species '{genus} - {common_name}' added successfully!")
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def show(
    name: Annotated[Optional[str], typer.Option(help="Search plants by nickname")] = None,
    species: Annotated[bool, typer.Option(help="Show Species (True / False)")] = False,
    due: Annotated[bool, typer.Option(help="Show only plants due for watering (True / False)")] = False,
) -> None:
    """
    Show plants in the database.

    Parameters
    ----------
    name : str
        If provided, show a single plant matching the nickname
    species : bool
        If True, show plant species instead of my plants
    due : bool
        If True, show only plants due for watering
    """

    if species and due:
        typer.echo("Error: Cannot use --species and --due together.")
        raise typer.Exit(code=1)

    if name and (species or due):
        typer.echo("Error: Cannot use --name with --species or --due.")
        raise typer.Exit(code=1)

    result = service.show_plants(name, species, due)

    if isinstance(result, list):
        if len(result) == 0 and name:
            typer.echo(f"No plants found with nickname '{name}'.")
        elif len(result) == 0 and not due:
            typer.echo("No plants in your collection yet. Try 'plantera add --help'.")
        elif len(result) == 0 and due:
            with db.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM my_plants")
                plants = cursor.fetchall()
                if len(plants) == 0:
                    typer.echo(
                        "No plants in your collection yet. Try 'plantera add --help'."
                    )
                else:
                    typer.echo("All plants are watered and up to date.")

        else:
            if not species:
                table = Table(
                    title="\nPlantera",
                    header_style="bold green",
                    border_style="green",
                    box=ROUNDED,
                    row_styles=["", "bold"],
                )

                table.add_column("Nickname")
                table.add_column("Genus")
                table.add_column("Common Name")
                table.add_column("Last Watered")
                table.add_column("Next Watering")
                table.add_column("Interval")

                if name:
                    table.add_column("Environment")
                    table.add_column("Care Info")

                for plant in result:
                    next_watering_date = date.fromisoformat(plant["next_watering"])
                    if plant["next_watering"] < str(date.today()):
                        next_watering = (
                            f"[red]{humanize.naturalday(next_watering_date)}[/red]"
                        )
                    else:
                        next_watering = humanize.naturalday(next_watering_date)

                    if name:
                      table.add_row(
                        plant["nickname"],
                        plant["genus"],
                        plant["common_name"],
                        humanize.naturalday(
                          date.fromisoformat(plant["last_watered"])
                        ),
                        next_watering,
                        f"{str(plant['interval'])} {'day' if plant['interval'] == 1 else 'days'}",
                        plant["environment"],
                        plant["care_info"],
                      )
                    else:
                        table.add_row(
                            plant["nickname"],
                            plant["genus"],
                            plant["common_name"],
                            humanize.naturalday(
                                date.fromisoformat(plant["last_watered"])
                            ),
                            next_watering,
                            f"{str(plant['interval'])} {'day' if plant['interval'] == 1 else 'days'}",
                        )

                Console().print(table)
            else:
                # Plant Species table
                table = Table(
                    title="\nPlant Species",
                    header_style="bold green",
                    border_style="green",
                    box=ROUNDED,
                    row_styles=["", "bold"],
                )

                table.add_column("ID")
                table.add_column("Genus")
                table.add_column("Common Name")
                table.add_column("Care Info")

                for row in result:
                    table.add_row(
                        str(row["id"]),
                        row["genus"],
                        row["common_name"],
                        row["care_info"],
                    )

                Console().print(table)

    else:
        typer.echo(result)
        raise typer.Exit(code=1)


@app.command()
def watered(nickname: Annotated[str, typer.Argument(help="Mark plant as watered (Plant nickname)")]) -> None:
  """
  Mark a plant as watered and recalculate its next watering date.

  Parameters
  ----------
  nickname : str
      The plant's nickname
  """

  success, result = service.watered(nickname)

  if success:
    typer.echo(f"Plant '{nickname}' marked as watered, next watering is {humanize.naturalday(result)}.")
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def snooze(
    nickname: Annotated[str, typer.Argument(help="The nickname of the plant you wish to delay watering (snooze)")],
    days: Annotated[int, typer.Argument(help="The number of days to delay watering the plant")] = 1
) -> None:
  """
  Delay a plant's next watering date by a given number of days.

  Parameters
  ----------
  nickname : str
      The plant's nickname
  days : int
      Number of days to snooze — must be between 1 and 365
  """

  if days < 1:
    typer.echo("Error: Number of days must be greater than 0.")
    raise typer.Exit(code=1)

  if days > 365:
    typer.echo("Error: That's a long time to not water a plant! Number of days must be less than or equal to 365.")
    raise typer.Exit(code=1)

  success, result = service.snooze(nickname, days)

  if success is True:
    typer.echo(f"Plant '{nickname}' snoozed for {days} days.")
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def update(
    my_plant: Annotated[str, typer.Argument(help="Nickname of the plant to update")],
    nickname: Annotated[Optional[str], typer.Option(help="New nickname of the plant")] = None,
    genus: Annotated[Optional[str], typer.Option(help="genus of the plant (must exist in the database)")] = None,
    last_watered: Annotated[Optional[str], typer.Option(help="Last watered date (YYYY-MM-DD)")] = None,
    next_watering: Annotated[Optional[str], typer.Option(help="Next watering date (YYYY-MM-DD)")] = None,
    interval: Annotated[Optional[int], typer.Option(help="Watering interval (in days)")] = None,
    environment: Annotated[Optional[str], typer.Option(help="Description of the location and physical environment of the plant")] = None
) -> None:
  """
  Update a plant in the database.

  Parameters
  ----------
  my_plant : str
      Nickname of the plant to update
  nickname : str, optional
      New nickname for the plant
  genus : str, optional
      New genus (must exist in plant_species table)
  last_watered : str, optional
      New last watered date in YYYY-MM-DD format
  next_watering : str, optional
      Override next watering date in YYYY-MM-DD format
  interval : int, optional
      New watering interval in days
  environment : str, optional
      Updated description of the plant's environment
  """

  result = service.update_plant(my_plant, nickname, genus, last_watered, next_watering, interval, environment)

  if result is True:
    typer.echo(f"Plant '{my_plant}' updated successfully!")
  elif isinstance(result, str):
    typer.echo(result)
    raise typer.Exit(code=1)
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def update_species(
    genus_to_update: Annotated[str, typer.Argument(help="Genus of the plant to update")],
    genus: Annotated[Optional[str], typer.Option(help="New genus of the plant")] = None,
    common_name: Annotated[Optional[str], typer.Option(help="New common name of the plant")] = None,
    care_info: Annotated[Optional[str], typer.Option(help="Updated care information for the plant")] = None
) -> None:
  """
  Update a plant species in the database.

  Parameters
  ----------
  genus_to_update : str
      Genus of the species to update
  genus : str, optional
      New genus name
  common_name : str, optional
      New common name
  care_info : str, optional
      Updated care instructions
  """

  result = service.update_species(genus_to_update, genus, common_name, care_info)

  if result is True:
    typer.echo(f"Species '{genus_to_update}' updated successfully!")
  elif isinstance(result, str):
    typer.echo(result)
    raise typer.Exit(code=1)
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def delete(nickname: Annotated[str, typer.Argument(help="Nickname of the plant to delete")]) -> None:
  """
  Delete a plant from the database.

  Parameters
  ----------
  nickname : str
      Nickname of the plant to delete
  """

  if not typer.confirm(f"Are you sure you want to delete plant '{nickname}'?"):
    typer.echo("Deletion cancelled.")
    return

  result = service.delete_plant(nickname)

  if result is True:
    typer.echo(f"Plant '{nickname}' deleted successfully!")
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def delete_species(genus: Annotated[str, typer.Argument(help="Genus of the plant to delete")]) -> None:
  """
  Delete a plant species from the database.

  Parameters
  ----------
  genus : str
      Genus of the species to delete
  """

  if not typer.confirm(f"Are you sure you want to delete species '{genus}'?"):
    typer.echo("Deletion cancelled.")
    return

  result = service.delete_species(genus)

  if result is True:
    typer.echo(f"Species '{genus}' deleted successfully!")
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def remind() -> None:
  """Send a system notification for plants due for watering."""

  plants = service.show_plants(None, False, True)
  if len(plants) > 0:
    reminders = []
    for plant in plants:
      next_watering = date.fromisoformat(plant['next_watering'])
      reminders.append(f"Water {plant['nickname']} - {plant['common_name']} (Due: {humanize.naturalday(next_watering)})")
    title = "Water Reminder"
    message = '\n'.join(reminders)
    typer.echo(message)

    if sys.platform == "linux":
      # If on Linux, use notify-send to send the notification. Plyer doesn't respect the timeout parameter.
      subprocess.call(["notify-send", "-t", "10000", "-a", "Plantera", title, message])
    else:
      from plyer import notification
      notification.notify(title=title, message=message, timeout=10)
  else:
    typer.echo("No plants are due for watering.")


@app.command()
def config(
    setting: Annotated[Optional[str], typer.Argument(help="The setting to enable or update (auto_interval, claude_api_key [CLAUDE])")] = None,
    value: Annotated[Optional[str], typer.Option(help="Set the value of the setting")] = None,
    delete: Annotated[bool, typer.Option(help="Delete the setting")] = False
) -> None:
  """
  View or update Plantera settings.

  Run without arguments to display all current settings. Provide a setting name
  to update or delete it.

  Parameters
  ----------
  setting : str, optional
      The setting key to update or delete. Allowed values: auto_interval, claude_api_key.
  value : str, optional
      The value to set for the given setting.
  delete : bool
      If True, delete the setting row rather than updating it.
  """

  if value and delete:
    typer.echo("Error: Cannot use --value and --delete together.")
    raise typer.Exit(code=1)

  if setting is not None:
    setting = setting.replace('-', '_')

  if setting is None:
    result = service.get_settings()

    if result is not None:
      if isinstance(result, list):
        if len(result) == 0:
          typer.echo("There are no settings configured.")
        else:
          table = Table(title="\nSettings", header_style="bold green", border_style="green", box=ROUNDED,
                        row_styles=["", "bold"])

          table.add_column("Setting Name")
          table.add_column("Value")

          for setting in result:
            table.add_row(
              setting['key'],
              setting['value']
            )

          Console().print(table)
      else:
        typer.echo(result)
        raise typer.Exit(code=1)

      return


  # Setting value must exist and be in the ALLOWED_SETTINGS list.
  if setting not in ALLOWED_SETTINGS:
    typer.echo(f"Error: Invalid setting. Allowed settings are: {', '.join(ALLOWED_SETTINGS)}")
    raise typer.Exit(code=1)

  if setting == "claude_api_key" and value is None:
    typer.echo("Error: claude_api_key requires a value.")
    raise typer.Exit(code=1)

  # auto_interval defaults to 0.4 (EMA alpha) when no value is provided.
  if setting == "auto_interval" and value is None:
    value = '0.4'

  result = service.config_setting(setting, value, delete)

  if result is True:
    typer.echo(f"Setting '{setting}' updated successfully!")
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def update_care_info(
    genus: Annotated[str, typer.Argument(help="Genus of the plant species to update")],
) -> None:
  """
  Fetch and update care info for a species using the Claude API.

  Parameters
  ----------
  genus : str
      Genus of the species to update (must exist in plant_species table)
  """

  success, result = service.update_care_info(genus)
  if success:
    console.print(f"\n[bold green]Response from Claude:[/bold green]")
    typer.echo(result)
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


@app.command()
def diagnose(
    nickname: Annotated[str, typer.Argument(help="The nickname of the plant you wish to diagnose")],
    condition: Annotated[Optional[str], typer.Option(help="Text description of plant's condition")] = None,
    picture: Annotated[Optional[str], typer.Option(help="Path to picture of plant")] = None,
) -> None:
  """
  Diagnose a plant's condition using the Claude API.

  Parameters
  ----------
  nickname : str
      The plant's nickname (must exist in my_plants)
  condition : str, optional
      Text description of the observed condition (e.g. "Brown leaves")
  picture : str, optional
      Path to an image file to include in the diagnosis
  """

  if condition is None and picture is None:
    typer.echo("Error: You must provide either a condition or a picture to diagnose the plant.")
    raise typer.Exit(code=1)

  success, result = service.diagnose(nickname, condition, picture)
  if success:
    console.print(f"\n[bold green]Response from Claude:[/bold green]\n")
    for chunk in result:
      print(chunk, end="", flush=True)
    print()
  else:
    typer.echo(str(result))
    raise typer.Exit(code=1)


if __name__ == "__main__":
  app()